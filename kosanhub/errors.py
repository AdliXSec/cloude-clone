"""Error terstruktur untuk API: dipakai service maupun route."""
from flask import jsonify


class ApiError(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, code=None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.code = code or self.__class__.__name__

    def to_response(self):
        resp = jsonify({"error": self.code, "message": self.message})
        resp.status_code = self.status_code
        return resp


class ValidationError(ApiError):
    status_code = 422


class NotFoundError(ApiError):
    status_code = 404


class ConflictError(ApiError):
    status_code = 409


def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def _api_error(err):
        return err.to_response()

    @app.errorhandler(404)
    def _not_found(_):
        resp = jsonify({"error": "NotFound", "message": "Resource tidak ditemukan"})
        resp.status_code = 404
        return resp

    @app.errorhandler(405)
    def _method_not_allowed(_):
        resp = jsonify({"error": "MethodNotAllowed", "message": "Method tidak diizinkan"})
        resp.status_code = 405
        return resp
