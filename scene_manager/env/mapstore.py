"""Keeps texture maps we create (sky, HDRI) or that a setup points to (custom env map) alive in the
.max file, so switching setups reuses the same map instead of building a new one each time.

Storage: a second custom attribute on the scene root node with a key list and a map list.
It is separate from the setup JSON (core/storage.py) and safe to delete; maps are rebuilt.
"""
from pymxs import runtime as rt

_MXS = r"""
global SM_SceneManagerMapsCA
SM_SceneManagerMapsCA = attributes SceneManagerMaps attribID:#(0x5a3c1e11, 0x1b7d4f12)
(
    parameters main
    (
        sm_map_keys type:#stringTab tabSizeVariable:true
        sm_maps type:#maxObjectTab tabSizeVariable:true
    )
)
global SM_ensureMapStore
fn SM_ensureMapStore = (
    if not (isProperty rootNode #sm_map_keys) do custAttributes.add rootNode SM_SceneManagerMapsCA
    ok
)
global SM_storeMap
fn SM_storeMap key m = (
    SM_ensureMapStore()
    local i = findItem rootNode.sm_map_keys key
    if i == 0 then (append rootNode.sm_map_keys key; append rootNode.sm_maps m)
    else rootNode.sm_maps[i] = m
    m
)
global SM_getMap
fn SM_getMap key = (
    if not (isProperty rootNode #sm_map_keys) then undefined else (
        local i = findItem rootNode.sm_map_keys key
        if i == 0 then undefined else rootNode.sm_maps[i]
    )
)
global SM_mapKeys
fn SM_mapKeys = (if isProperty rootNode #sm_map_keys then (rootNode.sm_map_keys as array) else #())
global SM_setZRot
fn SM_setZRot n a = (n.transform = (rotateZMatrix a) * (transMatrix n.pos); ok)
global SM_getZRot
fn SM_getZRot n = (local v = n.transform.row1; atan2 v.y v.x)
"""
_defined = False


def _define():
    global _defined
    if not _defined:
        rt.execute(_MXS)
        _defined = True


def get(key):
    _define()
    return rt.SM_getMap(key)


def put(key, texmap):
    _define()
    rt.SM_storeMap(key, texmap)
    return texmap


def keys():
    _define()
    return [str(k) for k in rt.SM_mapKeys()]


def key_of(texmap):
    """Key under which this map is stored, or None."""
    if texmap is None:
        return None
    for k in keys():
        if get(k) == texmap:
            return k
    return None


def set_z_rotation(node, degrees):
    _define()
    rt.SM_setZRot(node, float(degrees))


def get_z_rotation(node):
    _define()
    return round(float(rt.SM_getZRot(node)) % 360.0, 2)
