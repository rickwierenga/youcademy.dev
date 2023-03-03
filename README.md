![](./.github/banner.png)

# YouCademy

Submission to the OpenAI stack hack. Demo available at [youcademy.dev](https://youcademy.dev).

Video demo: https://www.youtube.com/watch?v=tCjxlZquboY.

Made by Rick Wierenga, Pedro Nieto, Socrates Osorio and Tjalling van der Schaar.

## Running locally

You will need an OpenAI and Google Cloud API key.

Running the server:

```
OPENAI_API_KEY=x GCP_API_KEY=y python server.py
```

Running the worker:

```
OPENAI_API_KEY=x GCP_API_KEY=y python worker.py
```

On a Mac, you need to set `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES` for the worker to work properly
