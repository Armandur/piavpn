from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    pia_user: str
    pia_pass: str
    pia_region: str = "se_stockholm"
    pia_encryption: str = "strong"
    openvpn_protocol: str = "udp"
    proxy_port: int = 8888
    control_port: int = 8000

    configs_dir: str = "/data/configs"
    auth_file: str = "/tmp/pia-auth.txt"

    model_config = {"env_file": ".env"}


settings = Settings()
