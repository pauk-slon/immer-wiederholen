# Deployment

Copy this directory to the server and place your exercise database at `data/exercises.yaml`.

Create `.env` from the example and fill in `BOT_TOKEN`:

```bash
cp .env.example .env
```

Log in to the container registry (required to pull the image):

```bash
docker login ghcr.io -u token -p <your-github-token>
```

Then start the bot:

```bash
docker compose up -d
```
