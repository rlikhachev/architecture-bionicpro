import os


class Settings:
    def __init__(self):
        self.keycloak_url = os.getenv("KEYCLOAK_URL", "http://keycloak:8080")
        self.keycloak_public_url = os.getenv("KEYCLOAK_PUBLIC_URL", self.keycloak_url)
        self.keycloak_realm = os.getenv("KEYCLOAK_REALM", "reports-realm")
        self.client_id = os.getenv("AUTH_CLIENT_ID", "bionicpro-auth")
        self.client_secret = os.getenv("AUTH_CLIENT_SECRET", "bionicpro-auth-secret")
        self.auth_redirect_uri = os.getenv("AUTH_REDIRECT_URI", "http://localhost:8000/auth/callback")
        self.frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        self.reports_api_url = os.getenv("REPORTS_API_URL", "http://bionicpro-api:8000")
        self.session_ttl_seconds = int(os.getenv("SESSION_TTL_SECONDS", "28800"))
        self.cookie_secure = os.getenv("COOKIE_SECURE", "true").lower() in ("1", "true", "yes")
        self.auth_secret_key = os.getenv("AUTH_SECRET_KEY", "dev-only-secret-key")


settings = Settings()
