import os


class Settings:
    def __init__(self):
        self.keycloak_url = os.getenv("KEYCLOAK_URL", "http://keycloak:8080")
        self.keycloak_realm = os.getenv("KEYCLOAK_REALM", "reports-realm")
        self.expected_audience = os.getenv("TOKEN_AUDIENCE", "reports-api")
        self.clickhouse_host = os.getenv("CLICKHOUSE_HOST", "clickhouse")
        self.clickhouse_port = int(os.getenv("CLICKHOUSE_PORT", "8123"))
        self.default_report_days = int(os.getenv("DEFAULT_REPORT_DAYS", "7"))
        self.s3_endpoint_url = os.getenv("S3_ENDPOINT_URL", "http://minio:9000")
        self.s3_access_key = os.getenv("S3_ACCESS_KEY", "bionicpro")
        self.s3_secret_key = os.getenv("S3_SECRET_KEY", "bionicpro-secret")
        self.s3_bucket = os.getenv("S3_BUCKET", "reports")
        self.cdn_base_url = os.getenv("CDN_BASE_URL", "http://localhost:8081")

    @property
    def issuer_suffix(self) -> str:
        return f"/realms/{self.keycloak_realm}"


settings = Settings()
