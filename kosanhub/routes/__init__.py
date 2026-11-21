"""Registrasi semua blueprint."""


def register_blueprints(app):
    from kosanhub.auth import auth_bp, init_auth
    from kosanhub.routes.admin import admin_bp
    from kosanhub.routes.billing import bills_bp, payments_bp
    from kosanhub.routes.contracts import contracts_bp
    from kosanhub.routes.health import health_bp
    from kosanhub.routes.jobs import jobs_bp
    from kosanhub.routes.public import public_bp
    from kosanhub.routes.properties import properties_bp, rooms_bp
    from kosanhub.routes.tenants import tenants_bp
    from kosanhub.routes.web import web_bp

    init_auth(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(web_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(properties_bp, url_prefix="/api/properties")
    app.register_blueprint(rooms_bp, url_prefix="/api/rooms")
    app.register_blueprint(tenants_bp, url_prefix="/api/tenants")
    app.register_blueprint(contracts_bp, url_prefix="/api/contracts")
    app.register_blueprint(bills_bp, url_prefix="/api/bills")
    app.register_blueprint(payments_bp, url_prefix="/api/payments")
    app.register_blueprint(jobs_bp, url_prefix="/api/jobs")
