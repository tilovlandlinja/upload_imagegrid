import os
import pandas as pd
from datetime import datetime

class ImageUploadTracker:

   

    def __init__(self, tracking_file='image_upload_log.csv'):
        self.tracking_file = tracking_file
        # Sjekk om CSV-filen finnes, hvis ikke, opprett den med de ønskede feltene
        if not os.path.exists(self.tracking_file):
            # Opprett en tom DataFrame med de nødvendige kolonnene
            columns = self.get_columns()
            df = pd.DataFrame(columns=columns)
            # Lagre DataFrame som CSV med semikolon som separator og ANSI-tegnsett
            df.to_csv(self.tracking_file, sep=';', index=False, encoding='ansi')

    def get_columns(self):
       return [
                "filename",
                "Location",
                "objektnummer",
                "linje_navn",
                "linje_id",
                "driftsmerking",
                "erHistorisk",
                "kilde",
                "anleggstype",
                "filehash",
                "uploadtime",
                "updatetime",
                "status"
            ]
    
    def has_been_uploaded(self, filehash):
        """
        Sjekker om bildet allerede er lastet opp basert på filehash.
        """
        if os.path.exists(self.tracking_file):
            df = pd.read_csv(self.tracking_file, sep=';', encoding='ansi')
            # Sjekk om filehash finnes i DataFrame
            row = df[df['filehash'] == filehash]
            if not row.empty:
                return True, row.iloc[0]['uploadtime'], row.iloc[0]['updatetime']
        return False, None, None

    def log_upload(self, data):
        # Last inn eksisterende CSV, eller opprett en ny DataFrame hvis filen ikke finnes
        if os.path.exists(self.tracking_file):
            df = pd.read_csv(self.tracking_file, sep=';', encoding='ansi')
        else:
            columns = self.get_columns()
            df = pd.DataFrame(columns=columns)
        
        # Legg til den nye opplastingen i DataFrame
        new_data = pd.DataFrame([data], columns=df.columns)
        df = pd.concat([df, new_data], ignore_index=True)
        
        # Lagre DataFrame tilbake til CSV med semikolon som separator og ANSI-tegnsett
        df.to_csv(self.tracking_file, sep=';', index=False, encoding='ansi')
        print(f"Bildet {data[0]} ble lastet opp og logget med filehash {data[9]}.")

    def get_number_of_uploads(self):
        """
        Returnerer antall opplastinger i loggen.
        """
        if os.path.exists(self.tracking_file):
            df = pd.read_csv(self.tracking_file, sep=';', encoding='ansi')

            # Filtrer DataFrame for rader der status er 'opplastet' (eller tilsvarende)
            uploaded_df = df[df['status'] == 'ok']
            failed_df = df[df['status'] == 'failed']

            # Tell antall rader med status 'opplastet'
            #antall_opplastet = len(opplastet_df), len(failed_df)
            return len(uploaded_df), len(failed_df)
        return 0


# Eksempel på bruk
if __name__ == "__main__":
    imagegrid_log = "imagegrid_log.csv"

    # Opprett en tracker-instans med spesifisert loggfil
    tracker = ImageUploadTracker(imagegrid_log)

    # Eksempeldata for opplastingen
    filename = 'path_to_your_image.jpg'
    latitude = 62.293172
    longitude = 6.842709
    anleggstype = "Type A"
    anleggstype_n = "Type A Name"
    navn = "Example Name"
    driftsmerking = "1171-81"
    erhistorisk = "no"
    ergroft = "no"
    kilde = "sourceA"
    nettmelding_elsmart = "12345"
    erutvendig = "yes"
    erinnvendig = "no"
    filehash = "example_hash_value"  # Dette er hash for bildet
    uploadtime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    updatetime = uploadtime

    # Sjekk om bildet allerede er lastet opp basert på filehash
    is_uploaded, upload_time, update_time = tracker.has_been_uploaded(filehash)

    if is_uploaded:
        print(f"Bildet med hash {filehash} ble allerede lastet opp den {upload_time}, sist oppdatert {update_time}.")
    else:
        # Dataene som skal logges
        data = [filename, latitude, longitude, anleggstype, anleggstype_n, navn, driftsmerking, erhistorisk,
                ergroft, kilde, nettmelding_elsmart, erutvendig, erinnvendig, filehash, uploadtime, updatetime]

        # Logg opplastingen
        tracker.log_upload(data)
        print(f"Bildet med hash {filehash} er nå logget som lastet opp.")