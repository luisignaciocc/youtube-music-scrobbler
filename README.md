# YTMUSIC LAST.FM SCROBBLER

The YTMusic Last.fm Scrobbler is a Python package that allows you to fetch your YouTube Music listening history and scrobble it to Last.fm.

## Installation

1. Clone or download the repository to your local machine.

2. Install Conda by following the instructions on the official Conda website: [Conda Installation](https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html).

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

The program will start fetching your YouTube Music history and scrobbling it to Last.fm. Note that the maximum number of records that can be fetched from the history is 200. Also, since YouTube Music does not provide the playback timestamp for each song, the timestamp when the script is run will be used for all the songs.

## Using SQLite for tracking scrobbled songs

The YTMusic Last.fm Scrobbler uses a SQLite database to keep track of the songs that have already been scrobbled to Last.fm. This prevents the same songs from being repeatedly sent as scrobbles in subsequent runs of the script.

The logic for tracking scrobbled songs is located in the `for` loop that iterates over the history of songs fetched from YouTube Music:

```python
for item in history:
    # ...
    scrobble = cursor.execute(
        'SELECT * FROM scrobbles WHERE track_name = :trackName AND artist_name = :artistName AND album_name = :albumName AND scrobbled_at BETWEEN :last_week AND :now', {
            "trackName": record["trackName"],
            "artistName": record["artistName"],
            "albumName": record["albumName"],
            "last_week": last_week,
            "now": now
        }).fetchone()
    if scrobble:
        continue
    # ...
    cursor.execute('''
        INSERT INTO scrobbles (track_name, artist_name, album_name, scrobbled_at)
        VALUES (:trackName, :artistName, :albumName, :ts)
    ''', record)
    self.conn.commit()
```

The code checks if a song has already been scrobbled by querying the SQLite database. If a record is found for the same track, artist, album, and time period (current week), that song is skipped and the next one is processed.

If the song is not found in the database, it proceeds to send it as a new scrobble to Last.fm using the `lastpy` library. Then, it inserts the following record into the database:

```sql
INSERT INTO scrobbles (track_name, artist_name, album_name, scrobbled_at)
VALUES (:trackName, :artistName, :albumName, :ts)
```

This ensures that only songs that have not been scrobbled in the specified time period are sent to Last.fm.

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
