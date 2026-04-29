

#  AI + Blockchain Based Digital Voting System

## 📌 Overview

This project is a secure, full-stack digital voting platform that integrates AI-powered facial recognition with blockchain technology to ensure transparency, integrity, and one-person-one-vote enforcement. It eliminates the need for centralized control while maintaining trust and security in the voting process.

---

## 🚀 Features

* 🔐 **Facial Authentication**
  Uses OpenCV Haar Cascade for voter verification with histogram-based matching.

* ⛓️ **Blockchain Voting System**
  Custom Python blockchain using SHA-256 to store votes as immutable blocks.

* 🚫 **Duplicate Vote Prevention**
  Ensures each voter can vote only once by validating entries against the blockchain.

* 🧑‍💼 **Admin Panel**

  * Voter & Candidate Registration
  * Election Scheduling (time-locked voting)
  * Result Visibility Control
  * Audit Log (500 entries searchable)

* 📄 **Vote Receipt System**
  Generates downloadable PDF receipts with block index and hash.

* 💾 **Persistent Storage**
  Uses SQLite to maintain blockchain data across server restarts.

* 🌐 **REST API Backend**
  Built with Flask for handling authentication, voting, and results.

---

## 🏗️ Tech Stack

* **Backend:** Python, Flask
* **AI/ML:** OpenCV
* **Database:** SQLite
* **Blockchain:** Custom Python Implementation
* **Other:** PDF Generation, REST APIs

---

## 📂 Project Structure

```
├── app.py                 # Main Flask application
├── blockchain.py         # Blockchain logic
├── face_recognition.py   # AI authentication module
├── database.db           # SQLite database
├── templates/            # HTML templates
├── static/               # CSS/JS files
├── receipts/             # Generated PDF receipts
└── admin/                # Admin panel modules
```

---

## ⚙️ Installation

1. Clone the repository:

```bash
git clone https://github.com/your-username/your-repo-name.git
cd your-repo-name
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the application:

bash
python app.py


4. Open in browser:


http://127.0.0.1:5000/

## 🔄 API Endpoints

* `POST /api/verify-face` → Authenticate voter
* `POST /api/vote` → Cast vote
* `GET /api/results` → View results
* `GET /api/blockchain` → View blockchain data



## 🔍 How It Works

1. User registers and facial data is stored
2. During voting, face is verified
3. Vote is recorded as a blockchain block
4. Chain validation ensures no tampering
5. Receipt is generated for verification



## 🛡️ Security Highlights

* Immutable blockchain records
* Cryptographic hashing
* AI-based identity verification
* No centralized vote control



## 📈 Future Enhancements

* Live camera-based authentication
* Cloud deployment (AWS/GCP)
* Mobile app integration
* Advanced ML models for higher accuracy


## 🤝 Contributing

Pull requests are welcome. For major changes, open an issue first to discuss your ideas.



## 📜 License

This project is open-source and available under the MIT License.

