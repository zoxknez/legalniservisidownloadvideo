"""RTS Planeta video download service - stub for future implementation."""

class RtsDownloader:
    """RTS Planeta downloader stub."""
    
    def __init__(self, auth=None, output_dir: str = './output'):
        self.auth = auth
        self.output_dir = output_dir

    def download_video(self, video_id: int, **kwargs):
        """Download video stub."""
        raise NotImplementedError("RTS Planeta downloader not yet fully implemented in core services")
