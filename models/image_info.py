import os
from datetime import datetime
from typing import Optional, Dict, Any, Union, List

class ImageInfo:
    def __init__(self):
        self.default_values = {
            'Location': None,
            'Objektnummer': '',
            'Anleggstype': '',
            'Anleggstype_n': '',
            'driftsmerking': '',
            'erhistorisk': False,
            'ergroft': '',
            'kilde': '',
            'nettmelding_elsmart': '',
            'erutvendig': 0,
            'erinnvendig': 0,
            'filehash': '',
            'mstasjon': ''
        }
        
        # Standard log columns for CSV tracking
        self.log_columns = [
            'filename', 'filepath', 'Location', 'avstand', 'objektnummer', 
            'linje_navn', 'linje_id', 'driftsmerking', 'erHistorisk', 'kilde', 
            'anleggstype', 'filehash', 'uploadtime', 'updatetime', 'status'
        ]

    def create_location(self, latitude: Optional[float], longitude: Optional[float]) -> Optional[Dict[str, Any]]:
        """Create a location dictionary if coordinates are valid."""
        if latitude is not None and longitude is not None:
            return {"type": "Point", "coordinates": [latitude, longitude]}
        return None

    def create_nettstasjon_info(
        self,
        navn: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        objektnummer: str = '',
        driftsmerking: str = '',
        kilde: str = '',
        filehash: str = '',
        mstasjon: str = '',
        **kwargs
    ) -> Dict[str, Any]:
        """Create image info for nettstasjon images."""
        imageinfo = self.default_values.copy()
        
        imageinfo.update({
            'navn': navn,
            'Location': self.create_location(latitude, longitude),
            'objektnummer': objektnummer,
            'Anleggstype': 'Nettstasjon',
            'Anleggstype_n': 'Nettstasjon',
            'driftsmerking': driftsmerking,
            'erhistorisk': False,
            'kilde': kilde,
            'filehash': filehash,
            'mstasjon': mstasjon
        })
        
        # Update with any additional kwargs
        imageinfo.update(kwargs)
        
        return imageinfo

    def create_toppbefaring_info(
        self,
        filename: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        objektnummer: str = '',
        linje_navn: str = '',
        linje_id: str = '',
        driftsmerking: str = '',
        kilde: str = '',
        filehash: str = '',
        **kwargs
    ) -> Dict[str, Any]:
        """Create image info for toppbefaring images."""
        imageinfo = self.default_values.copy()
        
        imageinfo.update({
            'filename': filename,
            'Location': self.create_location(latitude, longitude),
            'objektnummer': objektnummer,
            'anleggstype': 'MS',
            'anleggstype_n': 'Mast/stolpe',
            'driftsmerking': driftsmerking,
            'erHistorisk': False,
            'kilde': kilde,
            'filehash': filehash,
            'linje_navn': linje_navn,
            'linje_id': linje_id
        })
        
        # Update with any additional kwargs
        imageinfo.update(kwargs)
        
        return imageinfo

    def create_custom_info(
        self,
        filename: str,
        anleggstype: str,
        kilde: str,
        filehash: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Create custom image info with specified type."""
        imageinfo = self.default_values.copy()
        
        imageinfo.update({
            'filename': filename,
            'anleggstype': anleggstype,
            'anleggstype_n': anleggstype,
            'kilde': kilde,
            'filehash': filehash
        })
        
        # Update with any additional kwargs
        imageinfo.update(kwargs)
        
        return imageinfo

    def create_log_data(
        self,
        imageinfo: Dict[str, Any],
        filepath: str,
        status: str = 'ok',
        avstand: Optional[float] = None,
        linje_navn: str = '',
        linje_id: str = ''
    ) -> List[Any]:
        """Create standardized log data from imageinfo dictionary."""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        return [
            imageinfo.get('filename', ''),
            filepath,
            imageinfo.get('Location', ''),
            avstand or '',
            imageinfo.get('objektnummer', ''),
            linje_navn,
            linje_id,
            imageinfo.get('driftsmerking', ''),
            imageinfo.get('erHistorisk', ''),
            imageinfo.get('kilde', ''),
            imageinfo.get('anleggstype', ''),
            imageinfo.get('filehash', ''),
            current_time,  # uploadtime
            current_time,  # updatetime
            status
        ]

    def create_nettstasjon_log_data(
        self,
        imageinfo: Dict[str, Any],
        filepath: str,
        status: str = 'ok'
    ) -> List[Any]:
        """Create log data specifically for nettstasjon images."""
        return self.create_log_data(
            imageinfo=imageinfo,
            filepath=filepath,
            status=status,
            avstand=None,  # No distance calculation for nettstasjon
            linje_navn='',  # No line info for nettstasjon
            linje_id=''
        )

    def create_toppbefaring_log_data(
        self,
        imageinfo: Dict[str, Any],
        filepath: str,
        status: str = 'ok',
        avstand: Optional[float] = None
    ) -> List[Any]:
        """Create log data specifically for toppbefaring images."""
        return self.create_log_data(
            imageinfo=imageinfo,
            filepath=filepath,
            status=status,
            avstand=avstand,
            linje_navn=imageinfo.get('linje_navn', ''),
            linje_id=imageinfo.get('linje_id', '')
        )

    def create_failed_log_data(
        self,
        filepath: str,
        filehash: str = 'unknown',
        kilde: str = '',
        anleggstype: str = ''
    ) -> List[Any]:
        """Create log data for failed uploads."""
        filename = os.path.basename(filepath)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        return [
            filename,      # filename
            filepath,      # filepath
            None,          # Location
            None,          # avstand
            None,          # objektnummer
            None,          # linje_navn
            None,          # linje_id
            None,          # driftsmerking
            None,          # erHistorisk
            kilde,         # kilde
            anleggstype,   # anleggstype
            filehash,      # filehash
            current_time,  # uploadtime
            current_time,  # updatetime
            'failed'       # status
        ]

    def get_log_headers(self) -> List[str]:
        """Get the standard CSV headers for logging."""
        return self.log_columns.copy()
