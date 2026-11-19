"""Renderer + curated render settings, one card per renderer (V-Ray, Corona, Arnold).

Each curated value lists the renderer property names it may have (they changed between versions);
the first one that exists on the renderer is used. Names marked CHECK were not verified in Max:
run  render_props("<word>")  through Claude, or showProperties renderers.current, to confirm.
Environment GI/reflection overrides belong to the Environment module (M3), not here.
"""
from ..core.module_base import Module, Prop
from ..core.registry import register
from ..render import rprops


class RProp(Prop):
    """A curated renderer value: `names` are candidate MAXScript property names, `values` maps enum labels."""

    def __init__(self, key, label, kind, names, values=None, **kw):
        if values:
            kw["options"] = list(values.keys())
        super().__init__(key, label, kind, **kw)
        self.names = names
        self.values = values or {}


@register
class RendererModule(Module):
    key = "renderer"
    label = "Renderer"
    order = 8          # before every module that sets renderer properties
    category = "render"
    column = "Renderer"
    props = [Prop("renderer", "Renderer", "enum", options=rprops.installed_kinds,   # only what this 3ds Max has
                  tip="Switching renderer starts it from its defaults; the settings cards below then apply.")]
    props[0].labels = rprops.KIND_LABELS

    def capture(self):
        return {"renderer": rprops.current_kind()}

    def apply(self, values, context):
        if values.get("renderer"):
            rprops.set_renderer(values["renderer"])

    def summary(self, values):
        return rprops.KIND_LABELS.get(values.get("renderer"), values.get("renderer") or "")


class RendererSettings(Module):
    """Base for the per-renderer curated settings cards."""
    kinds = ()          # renderer kinds this card is for
    order = 50
    category = "render"

    def available(self):
        return rprops.current_kind() in self.kinds

    def installed(self):
        return rprops.is_installed(*self.kinds)

    def capture(self):
        if not self.available():
            return {}
        r = rprops.current()
        out = {}
        for p in self.props:
            v = rprops.read(r, p.names)
            if v is None:
                continue
            if p.values:
                v = next((lab for lab, val in p.values.items() if val == v), str(v))
            out[p.key] = v
        return out

    def apply(self, values, context):
        wanted = {k: v for k, v in values.items() if v is not None}
        if not wanted:
            return
        if not self.available():
            return   # values for another renderer stay stored; they apply when that renderer is current
        r = rprops.current()
        missing = []
        for p in self.props:
            if p.key not in wanted:
                continue
            v = wanted[p.key]
            if p.values:
                v = p.values.get(v, v)
            if rprops.write(r, p.names, v) is None:
                missing.append(p.label)
        if missing:
            raise RuntimeError("not found on %s: %s" % (rprops.current_kind(), ", ".join(missing)))

    def summary(self, values):
        bits = []
        for k in self.summary_keys:
            if values.get(k) is not None:
                bits.append("%s %s" % (k.split("_")[0], values[k]))
        return ", ".join(bits)

    summary_keys = ()


@register
class VRaySettings(RendererSettings):
    key = "render_vray"
    label = "V-Ray settings"
    kinds = ("vray", "vray_gpu")
    column = None
    summary_keys = ("sampler", "noise")
    props = [
        RProp("sampler", "Image sampler", "enum", ["imageSampler_type_new", "imageSampler_type"],
              values={"bucket": 0, "progressive": 1}),
        RProp("noise", "Noise threshold", "float", ["twoLevel_threshold", "twoLevel_adaptiveThreshold"],
              minimum=0, maximum=1, decimals=4, step=0.001, tip="Bucket noise threshold (CHECK name)"),
        RProp("min_subdivs", "Min subdivs", "int", ["twoLevel_baseSubdivs"], minimum=1, maximum=100),
        RProp("max_subdivs", "Max subdivs", "int", ["twoLevel_fineSubdivs"], minimum=1, maximum=100),
        RProp("prog_noise", "Progressive noise", "float", ["progressive_noise_threshold", "progressive_noiseThreshold"],
              minimum=0, maximum=1, decimals=4, step=0.001),
        RProp("prog_time", "Progressive time", "float", ["progressive_max_render_time", "progressive_maxTime"],
              minimum=0, maximum=100000, decimals=1, suffix=" min", tip="0 = no limit (CHECK name)"),
        RProp("gi_on", "GI", "bool", ["gi_on"]),
        RProp("gi_primary", "GI primary", "enum", ["gi_primary_type"],
              values={"irradiance map": 0, "brute force": 2}),
        RProp("gi_secondary", "GI secondary", "enum", ["gi_secondary_type"],
              values={"none": 0, "brute force": 2, "light cache": 3}),
        RProp("lc_subdivs", "Light cache subdivs", "int", ["lightcache_subdivs"], minimum=1, maximum=100000),
        RProp("displacement", "Displacement", "bool", ["options_displacement"]),
        RProp("max_depth_on", "Limit ray depth", "bool", ["options_maxDepth_on", "options_overrideDepth_on"]),
        RProp("max_depth", "Max ray depth", "int", ["options_maxDepth", "options_overrideDepth"], minimum=1, maximum=100),
    ]


@register
class CoronaSettings(RendererSettings):
    key = "render_corona"
    label = "Corona settings"
    kinds = ("corona",)
    summary_keys = ("noise_limit", "pass_limit")
    props = [
        RProp("noise_limit", "Noise limit", "float", ["adaptivity_targetError", "progressive_noiseLimit"],
              minimum=0, maximum=100, decimals=2, step=0.5, suffix=" %", tip="0 = off (CHECK name)"),
        RProp("pass_limit", "Pass limit", "int", ["progressive_passLimit"], minimum=0, maximum=100000, tip="0 = off"),
        RProp("time_limit", "Time limit", "int", ["progressive_timeLimit"], minimum=0, maximum=10 ** 9,
              suffix=" ms", tip="0 = off. 60000 = 1 minute"),
        RProp("denoiser", "Denoiser", "int", ["denoise_filterType"], minimum=0, maximum=10,
              tip="Denoiser type number (CHECK values in Max: none / high quality / NVIDIA / Intel)"),
        RProp("denoise_amount", "Denoise amount", "float", ["denoise_blendAmount"], minimum=0, maximum=1, decimals=2, step=0.05),
        RProp("gi_primary", "GI primary solver", "int", ["gi_primarySolver"], minimum=0, maximum=5,
              tip="Solver number (CHECK: 0 path tracing)"),
        RProp("gi_secondary", "GI secondary solver", "int", ["gi_secondarySolver"], minimum=0, maximum=5,
              tip="Solver number (CHECK: UHD cache)"),
        RProp("max_depth", "Max ray depth", "int", ["shading_maxRayDepth", "maxRayDepth"], minimum=1, maximum=1000),
        RProp("max_sample", "Max sample intensity", "float", ["shading_maxSampleIntensity", "maxSampleIntensity"],
              minimum=0, maximum=100000, decimals=1, step=1),
        RProp("light_samples", "Light samples mult", "float", ["lights_samplesMult", "lights_samplesMultiplier"],
              minimum=0, maximum=1000, decimals=2, step=0.5),
        RProp("displacement", "Displacement", "bool", ["displace_enable", "geometry_displace_enable"]),
    ]


@register
class ArnoldSettings(RendererSettings):
    key = "render_arnold"
    label = "Arnold settings"
    kinds = ("arnold",)
    summary_keys = ("camera_aa",)
    props = [
        RProp("camera_aa", "Camera (AA) samples", "int", ["AA_samples", "aa_samples"], minimum=-3, maximum=100),
        RProp("adaptive", "Adaptive sampling", "bool", ["enable_adaptive_sampling", "adaptive_sampling"]),
        RProp("aa_max", "Max camera samples", "int", ["AA_samples_max", "aa_samples_max"], minimum=0, maximum=100),
        RProp("adaptive_threshold", "Adaptive threshold", "float", ["adaptive_threshold", "AA_adaptive_threshold", "aa_adaptive_threshold"],
              minimum=0, maximum=1, decimals=3, step=0.005),
        RProp("diffuse", "Diffuse samples", "int", ["GI_diffuse_samples", "gi_diffuse_samples"], minimum=0, maximum=100),
        RProp("specular", "Specular samples", "int", ["GI_specular_samples", "gi_specular_samples"], minimum=0, maximum=100),
        RProp("transmission", "Transmission samples", "int", ["GI_transmission_samples", "gi_transmission_samples"],
              minimum=0, maximum=100),
        RProp("sss", "SSS samples", "int", ["GI_sss_samples", "gi_sss_samples"], minimum=0, maximum=100),
        RProp("diffuse_depth", "Diffuse depth", "int", ["GI_diffuse_depth", "gi_diffuse_depth"], minimum=0, maximum=100),
        RProp("specular_depth", "Specular depth", "int", ["GI_specular_depth", "gi_specular_depth"], minimum=0, maximum=100),
        RProp("transmission_depth", "Transmission depth", "int", ["GI_transmission_depth", "gi_transmission_depth"],
              minimum=0, maximum=100),
    ]
