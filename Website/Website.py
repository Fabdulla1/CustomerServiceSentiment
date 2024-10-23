import reflex as rx
from hume.expression_measurement.batch import Language, Models  # For specifying language model
import asyncio
from datetime import datetime
from typing import List
from hume import AsyncHumeClient
from hume.expression_measurement.batch.types import UnionPredictResult
from dotenv import load_dotenv
import os
from urllib.parse import urlencode
import spotipy
from spotipy.oauth2 import SpotifyOAuth

load_dotenv(dotenv_path='./Website/.env')

HUME_API_KEY = os.getenv("HUME_API_KEY")
client = AsyncHumeClient(api_key=HUME_API_KEY)
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

# Scope for accessing user's top tracks
SCOPE = "user-top-read"
sp = None
class State(rx.State):
    """App state to manage user input and API response."""
    show_questions: bool = False
    user_input: str = ""
    emotion_result: dict = {}  # Store API result
    maxEmotion: str = ""
    maxVal: int = 0
    playlistName: str = ""
    def spotifyLogin(self):
        auth_manager = SpotifyOAuth(client_id=SPOTIPY_CLIENT_ID,
                                               client_secret=SPOTIPY_CLIENT_SECRET,
                                               redirect_uri=REDIRECT_URI,
                                               scope="user-library-read")
        sp = spotipy.Spotify(auth_manager=auth_manager)
        user = sp.current_user()
        self.show_questions = not (self.show_questions)
    def spotifyPlaylist(sp, emotion):
        # Search for playlists with the emotion in the title
        results = sp.search(q=f'playlist:{emotion}', type='playlist', limit=1)

        if results['playlists']['items']:
            playlist = results['playlists']['items'][0]
            playlist_id = playlist['id']
            playlist_name = playlist['name']

            sp.current_user_follow_playlist(playlist_id)
            return playlist_name
    def processSP(self):
        if sp:
            self.playlistName = self.spotifyPlaylist(sp, self.maxEmotion)

    def set_user_input(self, value: str):
        self.user_input = value
    def toggle_questions(self):
        """Toggle the visibility of questions."""
        self.show_questions = not self.show_questions

    def pageRefresh(self):
        """Reset state on page refresh."""
        self.show_questions = False
        self.emotion_result = ""  # Clear previous result

    async def apiHume(self):
        """Send user input to Hume AI API and store the result."""
        if not self.user_input:
            self.emotion_result = "Please enter some text!"
            return
        model = Language(granularity="sentence")
       # Start an inference job and print the job_id
        job_id = await client.expression_measurement.batch.start_inference_job(
            text=[self.user_input], models=Models(language=model)
        )
        print(f"Job ID: {job_id}")

        # Await the completion of the inference job with timeout and exponential backoff
        await poll_for_completion(client, job_id, timeout=120)

        # After the job is over, access its predictions
        job_predictions = await client.expression_measurement.batch.get_job_predictions(
            id=job_id
        )

        # Process and display the predictions
        def extract_emotions(data):
            # Initialize an empty dictionary to store total scores for each emotion
            emotion_scores = {}
            for file in job_predictions:
                for prediction in file.results.predictions:
                    for grouped_prediction in prediction.models.language.grouped_predictions:
                        for language_prediction in grouped_prediction.predictions:
                            for emotion in language_prediction.emotions:
                                    # Accumulate emotion scores
                                    emotion_scores[emotion.name] = emotion_scores.get(emotion.name, 0) + (emotion.score * 100)
            return emotion_scores
                
        self.emotion_result = extract_emotions(job_predictions)

        for i in self.emotion_result.keys():
            self.maxVal= max(self.emotion_result[i], self.maxVal)
        for i in self.emotion_result.keys():
            if self.emotion_result[i] == self.maxVal:
                self.maxEmotion = i
                break
        



async def poll_for_completion(client: AsyncHumeClient, job_id, timeout=120):
    """
    Polls for the completion of a job with a specified timeout (in seconds).

    Uses asyncio.wait_for to enforce a maximum waiting time.
    """
    try:
        # Wait for the job to complete or until the timeout is reached
        await asyncio.wait_for(poll_until_complete(client, job_id), timeout=timeout)
    except asyncio.TimeoutError:
        # Notify if the polling operation has timed out
        print(f"Polling timed out after {timeout} seconds.")

async def poll_until_complete(client: AsyncHumeClient, job_id):
    """
    Continuously polls the job status until it is completed, failed, or an unexpected status is encountered.

    Implements exponential backoff to reduce the frequency of requests over time.
    """
    last_status = None
    delay = 1  # Start with a 1-second delay

    while True:
        # Wait for the specified delay before making the next status check
        await asyncio.sleep(delay)

        # Retrieve the current job details
        job_details = await client.expression_measurement.batch.get_job_details(job_id)
        status = job_details.state.status

        # If the status has changed since the last check, print the new status
        if status != last_status:
            print(f"Status changed: {status}")
            last_status = status

        if status == "COMPLETED":
            # Job has completed successfully
            print("\nJob completed successfully:")
            # Convert timestamps from milliseconds to datetime objects
            created_time = datetime.fromtimestamp(job_details.state.created_timestamp_ms / 1000)
            started_time = datetime.fromtimestamp(job_details.state.started_timestamp_ms / 1000)
            ended_time = datetime.fromtimestamp(job_details.state.ended_timestamp_ms / 1000)
            # Print job details neatly
            print(f"  Created at: {created_time}")
            print(f"  Started at: {started_time}")
            print(f"  Ended at:   {ended_time}")
            print(f"  Number of errors: {job_details.state.num_errors}")
            print(f"  Number of predictions: {job_details.state.num_predictions}")
            break
        elif status == "FAILED":
            # Job has failed
            print("\nJob failed:")
            # Convert timestamps from milliseconds to datetime objects
            created_time = datetime.fromtimestamp(job_details.state.created_timestamp_ms / 1000)
            started_time = datetime.fromtimestamp(job_details.state.started_timestamp_ms / 1000)
            ended_time = datetime.fromtimestamp(job_details.state.ended_timestamp_ms / 1000)
            # Print error details neatly
            print(f"  Created at: {created_time}")
            print(f"  Started at: {started_time}")
            print(f"  Ended at:   {ended_time}")
            print(f"  Error message: {job_details.state.message}")
            break

        # Increase the delay exponentially, maxing out at 16 seconds
        delay = min(delay * 2, 16)


@rx.page(on_load=State.pageRefresh)
def index() -> rx.Component:
    
    """Main page layout."""
    return rx.vstack(
        # Home page view before clicking "Vibe Check"
        rx.cond(
            ~State.show_questions,
            rx.vstack(
                rx.text("Emotionfy", size='8'),
                rx.text("Welcome to the place where your feelings sing to you!"),
                rx.text(
                    "Login with Spotify and answer a few questions to let Hume AI analyze your emotional spectrum."
                ),
                rx.button("Login with Spotify", on_click=State.spotifyLogin),
            
            )
        ),
        # Questions and input field view
        rx.cond(
                State.show_questions,
                rx.vstack(
                    rx.text("How are you today?", size='4', margin="0.5rem 0"),
                    rx.input(
                        placeholder="Tell us how you really feel!",
                        value=State.user_input,
                        on_change=State.set_user_input,
                        size='5'
                    ),
                    rx.button(
                        "Process Your Emotions",
                        on_click=State.apiHume,  # Trigger API call
                    ),
                ),
            ),
        rx.cond(
            State.emotion_result,
            rx.stack(
                rx.text(f"You're probably feeling {State.maxEmotion} with a percent of {State.maxVal}%"),
                rx.cond(
                    State.playlistName != "",
                    rx.text(f"Your playlist name is {State.playlistName}. Enjoy!")
                )
            )
        ),
        height="100vh",
        style={
            "background": "radial-gradient(circle, rgba(107, 255, 184, 0.3) 0%, rgba(0, 0, 0, 0.9) 70%)",
            "display": "flex",
            "align-items": "center",
            "justify-content": "center",
            "padding": "2rem",
            "text-align": "center",
        },
    )

# Initialize the app and add the page
app = rx.App()
app.add_page(index)
