import os
import sqlite3
import time
import cv2
import face_recognition
import requests

CANAL = "ring-sentinel-rayen-2026"
URL_NTFY = f"https://ntfy.sh/{CANAL}"
DB_FILE = "sentinel.db"


def initialiser_bdd():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS personnes_autorisees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            role TEXT NOT NULL,
            photo_ref TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def recuperer_personnes():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT nom, role, photo_ref FROM personnes_autorisees")
    lignes = cursor.fetchall()
    conn.close()
    return lignes


def envoyer_alerte_ami(nom: str, role: str):
    requests.post(
        URL_NTFY,
        data=f"{nom} ({role}) est devant la porte.".encode("utf-8"),
        headers={
            "Title": "Porte d'entree : Visage reconnu",
            "Priority": "default",
            "Tags": "white_check_mark,house",
        },
    )
    print(f"[Alerte] Notification envoyee pour {nom}.")


def envoyer_alerte_inconnu(chemin_capture: str):
    with open(chemin_capture, "rb") as img:
        requests.post(
            URL_NTFY,
            data=img,
            headers={
                "Title": "INTRUSION : Inconnu detecte sur le flux",
                "Priority": "urgent",
                "Tags": "warning,rotating_light",
                "Filename": "inconnu_live.jpg",
                "Actions": "view, Appeler la police, tel:17",
            },
        )
    print("[Alerte] Alerte intrusion envoyee avec capture.")


def lancer_flux_webcam():
    initialiser_bdd()
    personnes = recuperer_personnes()

    print("[Ring Vision] Chargement des profils autorises...")
    encodages_connus = []
    noms_connus = []

    for nom, role, photo_ref in personnes:
        if os.path.exists(photo_ref):
            ref_img = face_recognition.load_image_file(photo_ref)
            encs = face_recognition.face_encodings(ref_img)
            if encs:
                encodages_connus.append(encs[0])
                noms_connus.append((nom, role))
                print(f" - Enregistre : {nom} ({role})")

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print(
            "[Erreur] Impossible d'acceder a la webcam (/dev/video0 introuvable)."
        )
        return

    print("\n[Ring Sentinel] Surveillance active. Appuie sur 'q' pour quitter.")

    derniere_alerte = 0
    COOLDOWN_SECONDES = 10
    frame_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1
        temps_actuel = time.time()

        # Analyse 1 image sur 4 pour conserver une bonne fluidite
        if frame_count % 4 == 0:
            # Redimensionnement a 50 % pour accelerer le calcul
            small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
            rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

            locs = face_recognition.face_locations(rgb_small_frame)
            encs = face_recognition.face_encodings(rgb_small_frame, locs)

            for (top, right, bottom, left), enc in zip(locs, encs):
                nom_affiche = "Inconnu"
                role_affiche = "Alerte"
                couleur = (0, 0, 255)  # Rouge

                if encodages_connus:
                    matches = face_recognition.compare_faces(
                        encodages_connus, enc, tolerance=0.52
                    )
                    if True in matches:
                        index = matches.index(True)
                        nom_affiche, role_affiche = noms_connus[index]
                        couleur = (0, 255, 0)  # Vert

                # Remise a l'echelle des coordonnees (x2)
                top *= 2
                right *= 2
                bottom *= 2
                left *= 2

                # Dessin du cadre et du label
                cv2.rectangle(frame, (left, top), (right, bottom), couleur, 2)
                cv2.rectangle(
                    frame,
                    (left, bottom - 30),
                    (right, bottom),
                    couleur,
                    cv2.FILLED,
                )
                cv2.putText(
                    frame,
                    f"{nom_affiche}",
                    (left + 6, bottom - 8),
                    cv2.FONT_HERSHEY_DUPLEX,
                    0.7,
                    (255, 255, 255),
                    1,
                )

                # Declenchement de la notification si le delai est ecoule
                if temps_actuel - derniere_alerte > COOLDOWN_SECONDES:
                    if nom_affiche == "Inconnu":
                        capture_path = "capture_intrusion.jpg"
                        cv2.imwrite(capture_path, frame)
                        envoyer_alerte_inconnu(capture_path)
                    else:
                        envoyer_alerte_ami(nom_affiche, role_affiche)

                    derniere_alerte = temps_actuel

        cv2.imshow("Ring Sentinel - Live Feed", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    lancer_flux_webcam()
