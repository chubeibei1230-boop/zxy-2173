SECRET_KEY = "your-secret-key-here-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

REWORK_THRESHOLD = 3
INSPECTION_OVERDUE_HOURS = 24
COLOR_DIFFERENCE_CLUSTER_THRESHOLD = 3
TEAM_HIGH_REWORK_RATE_THRESHOLD = 0.3

FAKE_USERS_DB = {
    "admin": {
        "username": "admin",
        "password": "admin123"
    }
}
