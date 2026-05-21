"""HRTi video download service - stub for future implementation."""

class HrtiDownloader:
    """HRTi downloader stub."""
    
    def __init__(self, auth=None, output_dir: str = './output'):
        self.auth = auth
        self.output_dir = output_dir

    def download_video(self, ref_id: str, **kwargs):
        """Download video stub."""
        raise NotImplementedError("HRTi downloader not yet fully implemented in core services")
