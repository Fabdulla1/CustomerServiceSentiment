import reflex as rx

class State(rx.State):
    """App state to track if questions are visible."""
    show_questions: bool = False  # Initial state

    def toggle_questions(self):
        """Set the visibility of the questions to True."""
        self.show_questions = not(self.show_questions)  # Hide the button and show questions
def question_set(question: str) -> rx.Component:
    """Create a set of question text and input box."""
    return rx.vstack(
        rx.text(question, font_size="20px", color="white", font_weight="bold"),
        rx.input(placeholder="Your answer...", width="300px"),
        spacing="10px"
    )

def index() -> rx.Component:
    """Main page layout with three questions."""
    return rx.box(
        rx.center(
            rx.vstack(
                question_set("How are you feeling today?"),
                question_set("What’s something exciting that happened recently?"),
                question_set("If you could describe your current mood in one word, what would it be?"),
                spacing="30px"  # Space between question sets
            ),
        ),
        height="100vh",
        style={
            "background": "radial-gradient(circle, rgba(107, 255, 184, 0.3) 0%, rgba(0, 0, 0, 0.9) 70%)",  # Flashlight effect with green
            "display": "flex",
            "align-items": "center",
            "justify-content": "center",
        },
    )

# Define and run the Reflex app
app = rx.App(state=State)
app.add_page(index)