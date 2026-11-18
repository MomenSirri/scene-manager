"""Claude Code tools for lighting & environment (M3). Loaded by mcp_server.py."""


def register(mcp, call):
    @mcp.tool()
    def environment_info() -> dict:
        """Sun, dome, environment (sky/HDRI), GI/reflection overrides, atmospherics and viewport background as they are now."""
        return call("environment_info")

    @mcp.tool()
    def sun_position(date: str, time: str, latitude: float | None = None, longitude: float | None = None,
                     utc_offset: float | None = None, city: str | None = None, north: float = 0.0) -> dict:
        """Calculate where the sun is (changes nothing). date YYYY-MM-DD, time HH:MM local. Azimuth 0 = north, 90 = east."""
        return call("sun_position", date=date, time=time, latitude=latitude, longitude=longitude,
                    utc_offset=utc_offset, city=city, north=north)

    @mcp.tool()
    def set_sun(azimuth: float | None = None, elevation: float | None = None, date: str | None = None,
                time: str | None = None, latitude: float | None = None, longitude: float | None = None,
                utc_offset: float | None = None, city: str | None = None, north: float | None = None,
                intensity: float | None = None, softness: float | None = None, shadows: bool | None = None,
                on: bool | None = None, sun_name: str | None = None, setup: str | None = None) -> dict:
        """Move and tune the sun. Either azimuth/elevation (degrees; azimuth 0 = +Y north, 90 = +X east) or
        date (YYYY-MM-DD) + time (HH:MM local) + latitude/longitude/utc_offset or city. north = where true north
        points in the scene, degrees clockwise from +Y. softness = sun size (bigger = softer shadows).
        setup = also store these values on that setup/folder. Returns the sun's values after the change."""
        return call("set_sun", azimuth=azimuth, elevation=elevation, date=date, time=time, latitude=latitude,
                    longitude=longitude, utc_offset=utc_offset, city=city, north=north, intensity=intensity,
                    softness=softness, shadows=shadows, on=on, sun_name=sun_name, setup=setup)

    @mcp.tool()
    def create_sun(name: str = "SM Sun", with_sky: bool = True) -> dict:
        """Create a V-Ray Sun or Corona Sun (by current renderer) and put the matching sky in the environment. Ask first."""
        return call("create_sun", name=name, with_sky=with_sky)

    @mcp.tool()
    def set_environment(mode: str, hdri_path: str | None = None, rotation: float | None = None,
                        intensity: float | None = None, custom_map: str | None = None, setup: str | None = None) -> dict:
        """Environment (what the camera sees): mode "none", "sky" (renderer sky linked to the sun), "hdri"
        (hdri_path, rotation degrees, intensity) or "custom" (custom_map = map name). Use list_hdris to find files."""
        return call("set_environment", mode=mode, hdri_path=hdri_path, rotation=rotation, intensity=intensity,
                    custom_map=custom_map, setup=setup)

    @mcp.tool()
    def set_env_overrides(gi_on: bool | None = None, gi_hdri: str | None = None, gi_rotation: float | None = None,
                          gi_intensity: float | None = None, refl_on: bool | None = None, refl_hdri: str | None = None,
                          refl_rotation: float | None = None, refl_intensity: float | None = None,
                          setup: str | None = None) -> dict:
        """Light the scene (GI) or feed reflections with a different HDRI than the background. V-Ray and Corona only."""
        return call("set_env_overrides", gi_on=gi_on, gi_hdri=gi_hdri, gi_rotation=gi_rotation,
                    gi_intensity=gi_intensity, refl_on=refl_on, refl_hdri=refl_hdri, refl_rotation=refl_rotation,
                    refl_intensity=refl_intensity, setup=setup)

    @mcp.tool()
    def set_dome(hdri_path: str | None = None, rotation: float | None = None, intensity: float | None = None,
                 on: bool | None = None, visible: bool | None = None, dome_name: str | None = None,
                 create: bool = False, setup: str | None = None) -> dict:
        """Dome light (V-Ray / Arnold): HDRI, rotation (degrees around Z), intensity, on, seen by camera.
        create=True makes a dome light if there is none (ask first)."""
        return call("set_dome", hdri_path=hdri_path, rotation=rotation, intensity=intensity, on=on,
                    visible=visible, dome_name=dome_name, create=create, setup=setup)

    @mcp.tool()
    def set_atmosphere(effects: dict, setup: str | None = None) -> dict:
        """Turn atmospheric effects on/off by name, e.g. {"VRayEnvironmentFog001": false}. See environment_info()."""
        return call("set_atmosphere", effects=effects, setup=setup)

    @mcp.tool()
    def list_hdris(search: str = "", folder: str | None = None, limit: int = 200) -> dict:
        """HDRI files in the user's favourite HDRI folders (or in `folder`), filtered by a name substring."""
        return call("list_hdris", search=search, folder=folder, limit=limit)
