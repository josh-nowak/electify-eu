import streamlit as st
import random
from trubrics.integrations.streamlit import FeedbackCollector
import os
import csv
import json
import random
from datetime import datetime
import base64
from pathlib import Path

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from RAG.models.RAG import RAG
from RAG.database.vector_database import VectorDatabase
from streamlit_app.utils.translate import translate
from streamlit_app.utils.support_widgets import support_button, support_banner
from streamlit.components.v1 import html


# Load dictionary with party names, image file paths, and links to manifestos
with open("streamlit_app/party_dict.json", "r") as file:
    party_dict = json.load(file)

# The following is necessary to make the code work for deploying on Streamlit Cloud.
# (We need a newer version of sqlite3 than the one provided by Streamlit.)
# The environment variable IS_DEPLOYED is created only in the Streamlit Secrets and set to the string "TRUE".
# if os.getenv("IS_DEPLOYED", default="FALSE") == "TRUE":
#     __import__("pysqlite3")
#     import sys

#     sys.modules["sqlite3"] = sys.modules["pysqlite3"]

# Streamlit page conifg
st.set_page_config(page_title="Electify", page_icon="🇪🇺", layout="centered")

##################################
### RAG SETUP ####################
##################################

DATABASE_DIR_MANIFESTOS = "./data/manifestos/chroma/openai"
DATABASE_DIR_DEBATES = "./data/debates/chroma/openai"
TEMPERATURE = 0.0
LARGE_LANGUAGE_MODEL = ChatOpenAI(
    model_name="gpt-3.5-turbo", max_tokens=400, temperature=TEMPERATURE
)


# Load the OpenAI embeddings model
@st.cache_resource
def load_embedding_model():
    return OpenAIEmbeddings(model="text-embedding-3-large")


embedding_model = load_embedding_model()


# Load the databases
@st.cache_resource
def load_db_manifestos():
    return VectorDatabase(
        embedding_model=embedding_model,
        source_type="manifestos",
        database_directory=DATABASE_DIR_MANIFESTOS,
    )


@st.cache_resource
def load_db_debates():
    return VectorDatabase(
        embedding_model=embedding_model,
        source_type="debates",
        database_directory=DATABASE_DIR_DEBATES,
    )


# Initialize RAG module with default parties
rag = RAG(
    databases=[load_db_manifestos(), load_db_debates()],
    parties=["cdu", "spd", "gruene", "fdp", "linke", "afd"],
    llm=LARGE_LANGUAGE_MODEL,
    k=3,
)

##################################
### TRUBRICS SETUP ###############
##################################
collector = FeedbackCollector(
    project="default",
    # for local testing, use environment variables:
    email=os.environ.get("TRUBRICS_EMAIL"),
    password=os.environ.get("TRUBRICS_PASSWORD"),
    # for deployment on Streamlit, use Streamlit secrets:
    # email=st.secrets.TRUBRICS_EMAIL,
    # password=st.secrets.TRUBRICS_PASSWORD,
)


##################################
### SESSION STATES ###############
##################################

# The "query" string will contain the user input (i.e., the question or keyword):
if "query" not in st.session_state:
    st.session_state.query = ""

# The "response" dictionary will contain the generated answer from the RAG system:
if "response" not in st.session_state:
    st.session_state.response = None

# The "stage" integer value will determine which part of the app is currently displayed:
if "stage" not in st.session_state:
    st.session_state.stage = 0

# The "language" string will determine the language of the interface and response:
if "language" not in st.session_state:
    st.session_state.language = "Deutsch"
else:
    rag.language = st.session_state.language

# The "parties" list determines which parties will be used for the RAG query:
if "parties" not in st.session_state:
    st.session_state.parties = rag.parties

# The "show_all_parties" boolean determines whether all party names are revealed or not:
if "show_all_parties" not in st.session_state:
    st.session_state.show_all_parties = True
    # Note that this will be overridden by the "show_individual_parties" dictionary below if the user reveals individual parties.

# The "show_individual_parties" dictionary will determine which party names are revealed in the app:
if "show_individual_parties" not in st.session_state:
    # The values in this dict will only be set true if a party name is explicitly "revealed" by the user.
    # The keys represent the (random) order of appearance of the parties in the app
    # and not fixed parties as opposed to the above party_dict.

    st.session_state.show_individual_parties = {
        f"party_{i+1}": False for i in range(len(st.session_state.parties))
    }

# The "example_prompts" dictionary will contain randomly selected example prompts for the user to choose from:
if "example_prompts" not in st.session_state:
    all_example_prompts = {}
    with open("streamlit_app/example_prompts.csv", "r") as file:
        reader = csv.DictReader(file, delimiter=";")
        for row in reader:
            for key, value in row.items():
                if key not in all_example_prompts:
                    all_example_prompts[key] = []
                all_example_prompts[key].append(value)

    st.session_state.example_prompts = {
        key: random.sample(value, 3) for key, value in all_example_prompts.items()
    }

if "number_of_requests" not in st.session_state:
    st.session_state.number_of_requests = 0

# The following variables are used to store the prompt and feedback with Trubrics:
if "use_trubrics" not in st.session_state:
    if "TRUBRICS_PASSWORD" in os.environ:
        st.session_state.use_trubrics = True
    else:
        st.session_state.use_trubrics = False
if "logged_prompt" not in st.session_state:
    st.session_state.logged_prompt = None
if "feedback" not in st.session_state:
    st.session_state.feedback = None
if "feedback_key" not in st.session_state:
    st.session_state.feedback_key = 0


##################################
### HELPER FUNCTIONS #############
##################################
def reveal_party(p):
    st.session_state.show_individual_parties[f"party_{p}"] = True


def img_to_bytes(img_path):
    img_bytes = Path(img_path).read_bytes()
    encoded = base64.b64encode(img_bytes).decode()
    return encoded


def img_to_html(img_path):
    img_html = "<img src='data:image/png;base64,{}' class='img-fluid' style='width:100%'>".format(
        img_to_bytes(img_path)
    )
    return img_html


def submit_query():
    st.session_state.logged_prompt = None
    st.session_state.response = None
    st.session_state.feedback = None
    st.session_state.stage = 1
    st.session_state.feedback_key += 1
    st.session_state.show_individual_parties = {
        f"party_{i+1}": False for i in range(len(st.session_state.parties))
    }
    random.shuffle(st.session_state.parties)


def set_query(query):
    st.session_state.query = query


def submit_example(query):
    set_query(query)
    submit_query()


def generate_response():
    max_retries = 2
    retry_count = 0
    while retry_count <= max_retries:
        try:
            print("Getting response")
            st.session_state.response = rag.query(query)

            # Assert that the response contains all parties
            assert set(st.session_state.response["answer"].keys()) == set(
                st.session_state.parties
            ), "LLM response does not contain all parties"
            break

        except Exception as e:
            print(f"An error occurred: {e}")
            # Error occured, increment retry counter
            retry_count += 1
            if retry_count > max_retries:
                print(f"Max number of tries ({max_retries}) reached, aborting")
                st.session_state.response = None
                st.error(
                    translate(
                        "Das Sprachmodell ist gerade nicht verfügbar. **Bitte versuche es gleich nochmal.**",
                        st.session_state.language,
                    )
                )
                # Display error message in app:
                raise e
            else:
                print(f"Retrying, retry number {retry_count}")
                pass


# The following function converts a date string from the format "YYYY-MM-DD" to "DD.MM.YYYY"
# (for display in the sources)
def convert_date_format(date_string):
    # Parse the date string into a datetime object
    date_obj = datetime.strptime(date_string, "%Y-%m-%d")

    # Format the datetime object into the new string format
    new_date_string = date_obj.strftime("%d.%m.%Y")

    return new_date_string


##################################
### USER INTERFACE ###############
##################################

with st.sidebar:
    selected_language = st.radio(
        label="Language",
        options=["🇩🇪 Deutsch", "🇬🇧 English"],
        horizontal=True,
    )
    languages = {"🇩🇪 Deutsch": "Deutsch", "🇬🇧 English": "English"}
    st.session_state.language = languages[selected_language]
    rag.language = st.session_state.language

st.header("🇪🇺 electify.eu", divider="blue")
st.write(
    "##### :grey["
    + translate(
        "Informiere dich über die Positionen der Parteien zur Europawahl 2024.",
        st.session_state.language,
    )
    + "]"
)

support_button(
    text=f"💙  {translate('Unterstützen', st.session_state.language)}",
    link="https://www.buymeacoffee.com/electify.eu",
)

if st.session_state.number_of_requests >= 3:
    # Show support banner after 3 requests in a single session.
    st.info(
        f"{translate('**Gefällt dir die App?** Mit einer kleinen Spende kannst du dafür sorgen, dass wir sie bis zur Europawahl weiterhin kostenlos anbieten können. [Jetzt unterstützen]', st.session_state.language)}(https://buymeacoffee.com/electify.eu)",
        icon="💙",
    )

query = st.text_input(
    label=translate(
        "Stelle eine Frage oder gib ein Stichwort ein",
        st.session_state.language,
    ),
    placeholder="",
    value=st.session_state.query,
)

col_submit, col_checkbox = st.columns([1, 3])

# Submit button
with col_submit:
    st.button(
        translate("Frage stellen", st.session_state.language),
        on_click=submit_query,
        type="primary",
    )

# Checkbox to show/hide party names globally
with col_checkbox:
    st.session_state.show_all_parties = st.checkbox(
        label=translate("Parteinamen anzeigen", st.session_state.language),
        value=True,
        help=translate(
            "Blende die Parteinamen aus, um Antworten unvoreingenommen lesen zu können.",
            st.session_state.language,
        ),
    )

# Allow the user to select up to 6 parties
with st.expander(translate("Parteien auswählen", st.session_state.language)):
    available_parties = list(party_dict.keys())

    party_selection = {party: False for party in available_parties}
    for party in st.session_state.parties:
        party_selection[party] = True

    def update_party_selection(party):
        party_selection[party] = not party_selection[party]
        st.session_state.parties = [k for k, v in party_selection.items() if v]

    st.write(
        translate(
            "Wähle bis zu 6 Parteien aus.",
            st.session_state.language,
        )
    )
    for party in available_parties:
        st.checkbox(
            label=party_dict[party]["name"],
            value=party_selection[party],
            on_change=update_party_selection,
            kwargs={"party": party},
        )

    if len(st.session_state.parties) == 0:
        st.markdown(
            f"⚠️ **:red[{translate('Bitte wähle mindestens eine Partei aus.', st.session_state.language)}]**"
        )
        # Reset to default parties
        st.session_state.parties = rag.parties
    elif len(st.session_state.parties) > 6:
        st.markdown(
            f"⚠️ **:red[{translate('Bitte wähle maximal sechs Parteien aus.', st.session_state.language)}]**"
        )
        # Limit to the six first selected parties
        st.session_state.parties = st.session_state.parties[:6]

    # Update the RAG module with the selected parties
    rag.parties = st.session_state.parties

# STAGE 0: User has not yet submitted a query
if st.session_state.stage == 0:
    st.write(translate("Beispiele:", st.session_state.language))

    for i in range(3):
        st.button(
            st.session_state.example_prompts[st.session_state.language][i],
            on_click=submit_example,
            args=(st.session_state.example_prompts[st.session_state.language][i],),
            key=f"example_prompt_{i}",
        )

# STAGE > 0: Show disclaimer once the user has submitted a query (and keep showing it)
if st.session_state.stage > 0:
    if len(st.session_state.parties) == 0:
        st.info(
            translate(
                "Wähle mindestens eine Partei in der Seitenleiste aus!",
                st.session_state.language,
            )
        )
        st.session_state.stage = 0

    else:
        st.info(
            "☝️ "
            + translate(
                "**Die Antworten werden von einem Sprachmodell generiert und können fehlerhaft sein.**",
                st.session_state.language,
            )
            + "  \n"
            + translate(
                "Bitte informiere dich zusätzlich in den verlinkten Wahlprogrammen.",
                st.session_state.language,
            )
            + "  \n\n"
            + translate(
                "Die Reihenfolge der angezeigten Parteien ist zufällig.",
                st.session_state.language,
            ),
        )

# STAGE 1: User submitted a query and we are waiting for the response
if st.session_state.stage == 1:
    st.session_state.number_of_requests += 1
    with st.spinner(
        translate(
            "Suche nach Antworten in Wahlprogrammen und Parlamentsdebatten...",
            st.session_state.language,
        )
        + "🕵️"
    ):
        generate_response()

    if st.session_state.use_trubrics:
        st.session_state.logged_prompt = collector.log_prompt(
            config_model={"model": LARGE_LANGUAGE_MODEL.model_name},
            prompt=query,
            generation=str(st.session_state.response),
        )

    st.session_state.stage = 2


# STAGE > 1: The response has been generated and is displayed
if st.session_state.stage > 1:

    # Initialize an empty list to hold all columns
    col_list = []
    # Create a pair of columns for each party
    num_parties = len(st.session_state.parties)
    col_list = [st.columns([0.3, 0.7]) for _ in range(num_parties)]

    # Show image and RAG response for each party
    for i, party in enumerate(st.session_state.parties):
        p = i + 1
        col1, col2 = col_list[i]

        most_relevant_manifesto_page_number = st.session_state.response["docs"][
            "manifestos"
        ][party][0].metadata["page"]

        show_party = (
            st.session_state.show_all_parties
            or st.session_state.show_individual_parties[f"party_{p}"]
        )

        # In this column, we show the party image
        with col1:
            st.write("\n" * 2)
            if show_party:
                file_loc = party_dict[party]["image"]
                st.markdown(img_to_html(file_loc), unsafe_allow_html=True)

            else:
                file_loc = "streamlit_app/assets/placeholder_logo.png"
                st.markdown(img_to_html(file_loc), unsafe_allow_html=True)
                st.button(
                    translate("Partei aufdecken", st.session_state.language),
                    on_click=reveal_party,
                    args=(p,),
                    key=p,
                )
        # In this column, we show the RAG response
        with col2:
            if show_party:
                st.header(party_dict[party]["name"])
            else:
                st.header(f"{translate('Partei', st.session_state.language)} {p}")

            st.write(st.session_state.response["answer"][party])
            if show_party:
                st.write(
                    f"""{translate('Mehr findest du im', st.session_state.language)} [{translate('Europawahlprogramm der Partei', st.session_state.language)} **{party_dict[party]['name']}** ({translate('z.B. Seite', st.session_state.language)} {most_relevant_manifesto_page_number + 1})]({party_dict[party]['manifesto_link']}#page={most_relevant_manifesto_page_number + 1})"""
                )

    st.markdown("---")

    # Display a section with all retrieved excerpts from the sources
    st.subheader(
        translate(
            "Quellen: Worauf basieren diese Antworten?", st.session_state.language
        )
    )
    st.write(
        translate(
            "Die Antworten wurden von dem KI-Sprachmodell GPT 3.5 generiert – unter Berücksichtigung der Wahlprogramme zur Europawahl 2024 und vergangener Reden im Europaparlament im Zeitraum 2019-2024.",
            st.session_state.language,
        )
    )
    st.write(
        translate(
            "Hier kannst du die genutzten Ausschnitte aus den Quellen einsehen:",
            st.session_state.language,
        )
    )
    for party in st.session_state.parties:
        with st.expander(
            translate(
                f"{translate('Quellen', st.session_state.language)}: {party_dict[party]['name']}",
                st.session_state.language,
            )
        ):
            for doc in st.session_state.response["docs"]["manifestos"][party]:
                manifesto_excerpt = doc.page_content.replace("\n", " ")
                page_number_of_excerpt = doc.metadata["page"] + 1
                link_to_manifesto_page = f"{party_dict[party]['manifesto_link']}#page={page_number_of_excerpt}"
                st.markdown(
                    f'[**Seite {page_number_of_excerpt} im Wahlprogramm**]({link_to_manifesto_page}): \n "{manifesto_excerpt}"\n\n'
                )
            for doc in st.session_state.response["docs"]["debates"][party]:
                debate_excerpt = doc.page_content.replace("\n", " ")
                date_of_excerpt = convert_date_format(doc.metadata["date"])
                speaker_of_excerpt = doc.metadata["fullName"]

                st.write(
                    f'**Ausschnitt aus einer Rede im EU-Parlament von {speaker_of_excerpt} am {date_of_excerpt}**: "{debate_excerpt}"\n\n'
                )

    st.markdown("---")

    # Show feedback section
    st.write(
        f"### {translate('Waren diese Antworten hilfreich für dich?', st.session_state.language)}"
    )
    st.write(
        translate(
            "Mit deinem Feedback hilfst du uns, die Qualität der Antworten zu verbessern.",
            st.session_state.language,
        )
    )

    if st.session_state.use_trubrics:
        st.session_state.feedback = collector.st_feedback(
            component="default",
            feedback_type="thumbs",
            model=LARGE_LANGUAGE_MODEL.model_name,
            prompt_id=st.session_state.logged_prompt.id,
            open_feedback_label="Weiteres Feedback (optional)",
            align="flex-start",
            key=f"feedback_{st.session_state.feedback_key}",
        )

        if st.session_state.feedback is not None:
            st.write(
                translate("Vielen Dank für dein Feedback!", st.session_state.language)
                + " 🙏"
            )
    else:
        st.write(
            "[Schicke uns gerne eine Nachricht](mailto:electify.eu@gmail.com) mit Anregungen oder Kritik. Wir freuen uns, von dir zu hören."
        )
