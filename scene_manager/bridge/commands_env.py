"""Claude bridge commands for lighting & environment (M3). Merged into commands.COMMANDS.

Each "set_*" command changes the scene now (one undo step). Pass `setup` to also store the same
values on that setup or folder, so the look survives switching setups.
"""
import os

import pymxs
from pymxs import runtime as rt

from ..core import nodes, registry, tokens
from ..core.manager import get_manager
from ..env import hdri, renderers, solar
from ..modules import sun as sun_mod
from .commands import log


def _apply_module(key, given, setup=None, undo_label="Claude"):
    """Merge `given` over the scene values, apply, and optionally store `given` on a setup."""
    m = registry.get(key)
    given = {k: v for k, v in given.items() if v is not None}
    with pymxs.undo(True, undo_label):
        values = m.capture()
        values.update(given)
        m.apply(values, tokens.base_context())
    rt.redrawViews()
    if setup:
        get_manager().set_values(setup, key, given)
    return m.capture()


def _sun_ref(sun_name):
    if not sun_name:
        return None
    n = rt.getNodeByName(sun_name)
    if n is None:
        raise KeyError("No node named %r" % sun_name)
    return nodes.ref(n)


def sun_position(date, time, latitude=None, longitude=None, utc_offset=None, city=None, north=0.0):
    """Pure calculation, changes nothing: solar azimuth/elevation and the scene azimuth."""
    if city:
        c = solar.find_city(city)
        if c is None:
            raise KeyError("Unknown city %r. Known: %s" % (city, ", ".join(sorted(solar.CITIES))))
        latitude = c[0] if latitude is None else latitude
        longitude = c[1] if longitude is None else longitude
        utc_offset = c[2] if utc_offset is None else utc_offset
    az, el = solar.sun_position(date, time, float(latitude), float(longitude), float(utc_offset or 0))
    return {"solar_azimuth": az, "elevation": el, "scene_azimuth": solar.scene_azimuth(az, north or 0),
            "below_horizon": el < 0, "latitude": latitude, "longitude": longitude, "utc_offset": utc_offset}


def set_sun(azimuth=None, elevation=None, date=None, time=None, latitude=None, longitude=None,
            utc_offset=None, city=None, north=None, intensity=None, softness=None, shadows=None,
            on=None, sun_name=None, setup=None):
    """Set the sun by angles OR by date/time/location, plus intensity, shadow softness, shadows on/off."""
    given = {"light": _sun_ref(sun_name), "on": on, "intensity": intensity, "size": softness, "shadows": shadows}
    if city:
        c = solar.find_city(city)
        if c is None:
            raise KeyError("Unknown city %r. Known: %s" % (city, ", ".join(sorted(solar.CITIES))))
        latitude = c[0] if latitude is None else latitude
        longitude = c[1] if longitude is None else longitude
        utc_offset = c[2] if utc_offset is None else utc_offset
    if date or time or latitude is not None or longitude is not None:
        given.update(position="date_time", date=date, time=time, latitude=latitude, longitude=longitude,
                     utc_offset=utc_offset, north=north)
    elif azimuth is not None or elevation is not None:
        given.update(position="angles", azimuth=azimuth, elevation=elevation)
    elif north is not None:
        given.update(north=north)
    if not given.get("light") and sun_mod.SunModule()._find() is None:
        raise RuntimeError("No sun light in the scene. Use create_sun first.")
    after = _apply_module("sun", given, setup, "Claude: sun")
    log("Sun -> %s" % ", ".join("%s=%s" % kv for kv in given.items() if kv[1] is not None and kv[0] != "light"))
    return after


def create_sun(name="SM Sun", with_sky=True):
    """Create a renderer sun (V-Ray Sun / Corona Sun) and, if with_sky, put the matching sky in the Environment slot."""
    with pymxs.undo(True, "Claude: create sun"):
        n = renderers.create_sun(name)
        if with_sky:
            from ..modules import environment
            renderers.set_background(environment.sky_for_scene())
    log("Created sun %s" % n.name)
    return {"sun": str(n.name), "class": str(rt.classOf(n))}


def set_environment(mode, hdri_path=None, rotation=None, intensity=None, custom_map=None, setup=None):
    """Environment mode none / sky / hdri / custom. hdri_path for hdri, custom_map (map name) for custom."""
    after = _apply_module("environment", {"mode": mode, "hdri": hdri_path, "rotation": rotation,
                                          "intensity": intensity, "custom_map": custom_map}, setup, "Claude: environment")
    if hdri_path:
        hdri.add_recent(hdri_path)
    log("Environment -> %s %s" % (mode, os.path.basename(hdri_path or "")))
    return after


def set_env_overrides(gi_on=None, gi_hdri=None, gi_rotation=None, gi_intensity=None,
                      refl_on=None, refl_hdri=None, refl_rotation=None, refl_intensity=None, setup=None):
    """GI / reflection environment overrides (V-Ray, Corona)."""
    after = _apply_module("env_override", dict(
        gi_on=gi_on, gi_hdri=gi_hdri, gi_rotation=gi_rotation, gi_intensity=gi_intensity,
        refl_on=refl_on, refl_hdri=refl_hdri, refl_rotation=refl_rotation, refl_intensity=refl_intensity),
        setup, "Claude: env overrides")
    log("Env overrides -> GI %s, refl %s" % (after.get("gi_on"), after.get("refl_on")))
    return after


def set_dome(hdri_path=None, rotation=None, intensity=None, on=None, visible=None, dome_name=None,
             create=False, setup=None):
    """Dome light (V-Ray / Arnold). create=True makes one if the scene has none."""
    ref = None
    if dome_name:
        n = rt.getNodeByName(dome_name)
        if n is None:
            raise KeyError("No node named %r" % dome_name)
        ref = nodes.ref(n)
    elif not renderers.list_domes():
        if not create:
            raise RuntimeError("No dome light in the scene. Pass create=True to make one.")
        with pymxs.undo(True, "Claude: create dome"):
            ref = nodes.ref(renderers.create_dome())
    after = _apply_module("dome", {"light": ref, "hdri": hdri_path, "rotation": rotation, "intensity": intensity,
                                   "on": on, "visible": visible}, setup, "Claude: dome")
    log("Dome -> %s" % ", ".join("%s=%s" % kv for kv in (("hdri", hdri_path), ("rotation", rotation),
                                                          ("intensity", intensity)) if kv[1] is not None))
    return after


def set_atmosphere(effects, setup=None):
    """Turn atmospheric effects on/off by name, e.g. {"VRayEnvironmentFog001": false}."""
    after = _apply_module("atmosphere", {"effects": dict(effects)}, setup, "Claude: atmosphere")
    log("Atmosphere -> %s" % effects)
    return after


def list_hdris(search="", folder=None, limit=200):
    """HDRIs in the user's favourite folders (or one folder)."""
    files = hdri.scan(folder, search=search) if folder else [e["path"] for e in hdri.library(search=search)]
    return {"favourites": hdri.load()["favourites"], "count": len(files), "hdris": files[:int(limit)]}


def environment_info():
    """Everything lighting/environment in the scene right now, per module."""
    out = {"renderer": tokens.renderer_name()}
    for key in ("sun", "dome", "environment", "env_override", "atmosphere", "viewport_bg"):
        m = registry.get(key)
        try:
            out[key] = m.capture() if m else None
        except Exception as e:
            out[key] = {"error": str(e)}
    out["suns"] = [str(s.name) for s in sun_mod.list_suns()]
    out["domes"] = [str(d.name) for d in renderers.list_domes()]
    return out


COMMANDS = {f.__name__: f for f in (
    sun_position, set_sun, create_sun, set_environment, set_env_overrides, set_dome, set_atmosphere,
    list_hdris, environment_info)}
