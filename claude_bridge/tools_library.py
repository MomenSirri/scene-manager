"""Claude Code tools for the environment / HDRI library (same library as the app's browser). Loaded by mcp_server.py."""


def register(mcp, call):
    @mcp.tool()
    def library_folders() -> dict:
        """Environment library roots (favourite folders, team HDRI folder), recent picks, and which slots
        (environment, dome, gi, refl) the current renderer supports."""
        return call("lib_roots")

    @mcp.tool()
    def browse_library(folder: str, search: str = "", images: bool = False) -> dict:
        """Subfolders and HDRI/EXR files of one library folder ("recent" for recent picks). With search, matching
        files in the whole subtree. images=True also lists jpg/png/tif environment images."""
        return call("lib_list", folder=folder, search=search, images=images)

    @mcp.tool()
    def use_library_asset(setup: str, target: str, path: str) -> dict:
        """Put a library file into a setup's slot: target "environment" (HDRI background), "dome" (dome light,
        created if the scene has none), "gi" or "refl" (V-Ray/Corona overrides). Stored on the setup; the scene
        changes at once only if the setup is active."""
        return call("lib_apply", id=setup, target=target, path=path)
