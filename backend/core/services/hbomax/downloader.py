"""HBO Max video download service - stub for future implementation."""

class HboMaxDownloader:
    """HBO Max downloader stub."""
    
    def __init__(self, auth=None, output_dir: str = './output'):
        self.auth = auth
        self.output_dir = output_dir

    def download_video(self, content_id: int, **kwargs):
        """Download video stub."""
        raise NotImplementedError("HBO Max downloader not yet fully implemented in core services")
