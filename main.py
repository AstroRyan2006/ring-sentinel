import os
import sqlite3
import time
import cv2
import numpy as np
from dotenv import load_dotenv
import face_recognition
import requests
from ring_client import RingSentinelClient

load_dotenv()

CANAL = os.getenv("NTFY_TOPIC", "ring-sentinel-rayen-2026")
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

def envoyer_alerte_ami(nom: str):
    """Notification pour les personnes de confiance / habitants."""
    requests.post(
        URL_NTFY,
        data=f"{nom} est devant la maison.".encode("utf-8"),
        headers={
            "Title": "Ring Sentinel : Entree",
            "Priority": "high",
            "Tags": "white_check_mark,house",
        },
    )
    print(f"[Alerte] Notification envoyee : {nom} est devant la maison.")

def envoyer_alerte_agent(role: str):
    """Notification pour les services, livreurs et secours."""
    requests.post(
        URL_NTFY,
        data=f"Un {role.lower()} est devant la maison.".encode("utf-8"),
        headers={
            "Title": "Ring Sentinel : Service / Livraison",
            "Priority": "high",
            "Tags": "package,bell",
        },
    )
    print(f"[Alerte] Notification envoyee : Un {role.lower()} est devant la maison.")

def envoyer_alerte_inconnu(chemin_capture: str, titre="INTRUSION : Inconnu detecte"):
    """Alerte rouge critique pour individu suspect ou masque."""
    with open(chemin_capture, "rb") as img:
        requests.post(
            URL_NTFY,
            data=img,
            headers={
                "Title": titre,
                "Priority": "urgent",
                "Tags": "warning,rotating_light",
                "Filename": "alerte_live.jpg",
                "Actions": "view, Appeler la police, tel:17",
            },
        )
    print(f"[Alerte] {titre} - Notification critique envoyee avec capture.")

def rehausser_luminosite(image):
    """Egalisation adaptative (CLAHE) pour flux sombre."""
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    cl = clahe.apply(l)
    return cv2.cvtColor(cv2.merge((cl, a, b)), cv2.COLOR_LAB2BGR)

def detecter_gilet_agent(zone_torse) -> bool:
    """Detecte la couleur fluo / haute visibilite d'un uniforme."""
    if zone_torse is None or zone_torse.size == 0:
        return False
    hsv = cv2.cvtColor(zone_torse, cv2.COLOR_BGR2HSV)
    bas_jaune = np.array([20, 90, 90])
    haut_jaune = np.array([40, 255, 255])
    masque = cv2.inRange(hsv, bas_jaune, haut_jaune)
    ratio = cv2.countNonZero(masque) / (zone_torse.shape[0] * zone_torse.shape[1])
    return ratio > 0.12

def lancer_flux_webcam():
    client_ring = RingSentinelClient()
    client_ring.verifier_session_ring()

    initialiser_bdd()
    personnes = recuperer_personnes()

    print("[Ring Vision] Chargement des profils enregistres...")
    encodages_connus = []
    donnees_connues = []

    for nom, role, photo_ref in personnes:
        if os.path.exists(photo_ref):
            ref_img = face_recognition.load_image_file(photo_ref)
            encs = face_recognition.face_encodings(ref_img)
            if encs:
                encodages_connus.append(encs[0])
                donnees_connues.append((nom, role))
                print(f" - Enregistre : {nom} ({role})")

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[Erreur] Webcam inaccessible.")
        return

    print("\n[Ring Sentinel] Surveillance active. 'q' pour quitter.")

    derniere_alerte = 0
    COOLDOWN_SECONDES = 5
    frame_count = 0
    visages_memorises = []
    prev_gray = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1
        temps_actuel = time.time()

        # Detection de presence
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        presence_detectee = False

        if prev_gray is not None:
            delta = cv2.absdiff(prev_gray, gray)
            thresh = cv2.threshold(delta, 25, 255, cv2.THRESH_BINARY)[1]
            if cv2.countNonZero(thresh) > 5000:
                presence_detectee = True
        prev_gray = gray

        if frame_count % 2 == 0:
            frame_optimisee = rehausser_luminosite(frame)
            rgb_frame = cv2.cvtColor(frame_optimisee, cv2.COLOR_BGR2RGB)

            locs = face_recognition.face_locations(rgb_frame, number_of_times_to_upsample=0)
            encs = face_recognition.face_encodings(rgb_frame, locs)

            visages_memorises = []

            if locs:
                for (top, right, bottom, left), enc in zip(locs, encs):
                    nom_identifie = None
                    role_identifie = None

                    if encodages_connus:
                        matches = face_recognition.compare_faces(encodages_connus, enc, tolerance=0.58)
                        if True in matches:
                            index = matches.index(True)
                            nom_identifie, role_identifie = donnees_connues[index]

                    # Verification d'un uniforme / gilet sur le torse
                    h_f, w_f, _ = frame.shape
                    y1 = min(h_f, bottom)
                    y2 = min(h_f, bottom + int((bottom - top) * 1.3))
                    x1 = max(0, left - 25)
                    x2 = min(w_f, right + 25)
                    zone_torse = frame[y1:y2, x1:x2]
                    porte_gilet = detecter_gilet_agent(zone_torse)

                    # Determination du statut d'affichage et de notification
                    if nom_identifie:
                        # Ami ou proche connu
                        texte_label = nom_identifie
                        couleur = (0, 255, 0)  # Vert
                        type_evenement = "ami"
                    elif porte_gilet or (role_identifie and role_identifie.lower() in ["livreur", "agent", "facteur"]):
                        # Agent / Livreur
                        role_final = role_identifie if role_identifie else "Livreur"
                        texte_label = f"Agent ({role_final})"
                        couleur = (0, 165, 255)  # Orange
                        type_evenement = "agent"
                    else:
                        # Inconnu non reference
                        texte_label = "Inconnu"
                        couleur = (0, 0, 255)  # Rouge
                        type_evenement = "inconnu"

                    visages_memorises.append((top, right, bottom, left, texte_label, couleur))

                    # Envoi de la notification appropriee
                    if temps_actuel - derniere_alerte > COOLDOWN_SECONDES:
                        if type_evenement == "ami":
                            envoyer_alerte_ami(nom_identifie)
                        elif type_evenement == "agent":
                            envoyer_alerte_agent(role_final)
                        else:
                            cv2.imwrite("capture_intrusion.jpg", frame)
                            envoyer_alerte_inconnu("capture_intrusion.jpg", "INTRUSION : Inconnu detecte")
                        derniere_alerte = temps_actuel

            elif presence_detectee:
                h, w, _ = frame.shape
                visages_memorises.append((int(h * 0.1), int(w * 0.9), int(h * 0.9), int(w * 0.1), "SUSPECT MASQUE / OBSTACLE", (0, 0, 255)))

                if temps_actuel - derniere_alerte > COOLDOWN_SECONDES:
                    cv2.imwrite("capture_intrusion.jpg", frame)
                    envoyer_alerte_inconnu("capture_intrusion.jpg", "ALERTE : Visage dissimule / Masque")
                    derniere_alerte = temps_actuel

        # Rendu continu des cadres
        for (top, right, bottom, left, label, couleur) in visages_memorises:
            cv2.rectangle(frame, (left, top), (right, bottom), couleur, 2)
            cv2.rectangle(frame, (left, bottom - 26), (right, bottom), couleur, cv2.FILLED)
            cv2.putText(
                frame,
                label,
                (left + 6, bottom - 6),
                cv2.FONT_HERSHEY_DUPLEX,
                0.6,
                (255, 255, 255),
                1,
            )

        cv2.imshow("Ring Sentinel - Live Feed", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    lancer_flux_webcam()
