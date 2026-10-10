# Ring Sentinel — Edge Computer Vision & Smart Access Control

Ring Sentinel integrates biometric edge intelligence with the Ring developer ecosystem. It captures live camera feeds, performs real-time facial recognition against a local SQLite database, and pushes actionable emergency alerts directly to mobile devices via ntfy.

## Features
- **Real-Time Video Pipeline:** Low-latency frame processing using OpenCV.
- **Biometric Edge Authentication:** Facial feature vector comparison using dlib and SQLite.
- **Ring Ecosystem Integration:** Architecture aligned with Ring Partner APIs (`api.amazonvision.com`) and private app specifications.
- **Instant Emergency Alerts:** Mobile push notifications with visual snapshots and interactive actions (e.g., immediate emergency calling).

## Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/AstroRyan2006/ring-sentinel.git
   cd ring-sentinel
   ```
   
2. **Set up the virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
   
3. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your ntfy topic and Ring credentials
   ```

4. **Initialize database & register trusted faces:**
   Place reference portraits in the project root and populate sentinel.db

5. **Run Ring Sentinel:**
   ```bash
   python main.py
   ```
