# YOUTUBE MUSIC LAST.FM SCROBBLER

The YTMusic Last.fm Scrobbler is a Python script that allows you to fetch your YouTube Music listening history from the last 24 hours and scrobble it to Last.fm.

## Installation

1. Clone or download the repository to your local machine.

2. We recommend using conda for managing the Python environment. Install Conda by following the instructions on the official Conda website: [Conda Installation](https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html) (You can also use another environment manager).

3. Create a new Conda environment using the provided `environment.yml` file:

```bash
conda env create -f environment.yml
```

This will create a new Conda environment named `ytmusic-scrobbler` with all the necessary dependencies.

4. Activate the Conda environment:

```bash
conda activate ytmusic-scrobbler
```

5. Run the following command to authenticate with YTMusic:

```bash
ytmusicapi oauth
```

Follow the instructions to complete the authentication. This will create an `oauth.json` file in the current directory.

6. Create an API key and API secret for Last.fm by following this link: [Create an API key and API secret for Last.fm](https://www.last.fm/api/account/create).

7. Create a `.env` file in the project's root directory and add the following information:

```
LASTFM_API_KEY=YOUR_LASTFM_API_KEY
LASTFM_API_SECRET=YOUR_LASTFM_API_SECRET
```

Replace `YOUR_LASTFM_API_KEY` with the API key you obtained from Last.fm and `YOUR_LASTFM_API_SECRET` with the corresponding API secret.

8. Run the following command to start scrobbling your YouTube Music history to Last.fm:

```bash
python start.py
```

The first time you run the script, it will start a web server and open a browser window for you to authenticate with Last.fm and grant access to the application. Once you have completed the authentication, a new entry will be added to the `.env` file called `LASTFM_SESSION`. This session token does not expire, and in subsequent runs of the script, you will not be prompted for authentication again or have the web server started.

The program will begin retrieving your YouTube Music history and scrobbling the tracks played on the same day you execute the script to Last.fm. It's important to note that a maximum of 200 records can be fetched from the history. Additionally, due to YouTube Music's limitation of not providing individual song playback timestamps, the timestamp of when the script is executed will be assigned to all the songs.

### Using SQLite for tracking scrobbled songs

The YTMusic Last.fm Scrobbler uses a SQLite database to keep track of the songs that have already been scrobbled to Last.fm. This prevents the same songs from being repeatedly sent as scrobbles in subsequent runs of the script.

## Deploy

To deploy this script, it is important to consider that it requires an authorization flow through the browser. Since it's not possible to perform this process directly on a server, it is recommended to follow the following approach:

1. Perform the initial execution of the script in your local environment. This will allow you to complete the authorization flow and establish the necessary sessions.

2. After completing the authorization in your local environment, you will need to manually upload two files to the server where the project is located: `.env` and `oauth.json`. These files contain the required configurations and sessions for subsequent executions.

3. Once the files are on the server, you can perform executions directly on it. The script will utilize the stored sessions in the loaded files to authorize and carry out its tasks.

Please note that this approach ensures that subsequent executions can be performed directly on the server without the need to repeat the authorization flow.

## Contributions

Contributions are welcome. If you would like to make improvements to the project, follow these steps:

1. Fork the repository.

2. Create a new branch for your feature or improvement:

```bash
git checkout -b feature/my-feature
```

3. Make your changes and commit them:

```bash
git commit -m "Add my feature"
```

4. Push your changes to your forked repository:

```bash
git push origin feature/my-feature
```

5. Open a pull request on the main repository.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more information.
