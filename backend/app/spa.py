from pathlib import PurePosixPath

from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles


class SPAStaticFiles(StaticFiles):
    """Serve assets e rotas React sem transformar erros da API em HTML."""

    async def get_response(self, path, scope):
        path = path.replace("\\", "/")
        if path.split("/", 1)[0] in {"api", "uploads", "health"}:
            raise HTTPException(status_code=404)
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or PurePosixPath(path).suffix or path.startswith("assets/"):
                raise
            if scope["method"] not in {"GET", "HEAD"}:
                raise
            return await super().get_response("index.html", scope)
