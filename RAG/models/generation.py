from langchain_openai import ChatOpenAI

from langchain_core.runnables import RunnablePassthrough, RunnableParallel

from langchain_core.output_parsers import StrOutputParser, JsonOutputParser

from langchain.prompts import PromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field

import sys

sys.path.append("RAG")
from database.vector_database import VectorDatabase
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

import random


# Deprecated: Output format for JSON parser
class PartySummaries(BaseModel):
    partei_a: str = Field(
        description="Antwort auf die Frage des Nutzers basierend auf den Positionen der Partei_A"
    )
    partei_b: str = Field(
        description="Antwort auf die Frage des Nutzers basierend auf den Positionen der Partei_B"
    )
    partei_c: str = Field(
        description="Antwort auf die Frage des Nutzers basierend auf den Positionen der Partei_C"
    )
    partei_d: str = Field(
        description="Antwort auf die Frage des Nutzers basierend auf den Positionen der Partei_D"
    )
    partei_e: str = Field(
        description="Antwort auf die Frage des Nutzers basierend auf den Positionen der Partei_E"
    )
    partei_f: str = Field(
        description="Antwort auf die Frage des Nutzers basierend auf den Positionen der Partei_F"
    )


# Deprecated
def rename_party(party: str, mode: str = "anonymize"):
    """
    Anonymizes or de-anonymizes party names.

    arguments:
    - party (str): party name
    - mode (str): "anonymize" or "deanonymize"

    returns:
    - party (str): anonymized party name
    """

    party_dict = {
        "cdu": "partei_a",
        "spd": "partei_b",
        "gruene": "partei_c",
        "linke": "partei_d",
        "fdp": "partei_e",
        "afd": "partei_f",
    }

    if mode == "anonymize":
        return party_dict[party.lower()]
    elif mode == "deanonymize":
        for key, value in party_dict.items():
            if value == party.lower():
                return key
    else:
        raise ValueError("mode must be 'anonymize' or 'deanonymize'")


# Deprecated
def get_documents_for_all_parties(self, query, k=5):
    sources = ["gruene", "spd", "cdu", "afd", "fdp", "linke"]

    random.shuffle(sources)

    docs = {}

    for source in sources:
        docs[source] = self.database.max_marginal_relevance_search(
            query, k=k, fetch_k=20, filter={"party": source}
        )
    return docs


def get_documents_for_party(db, query, party, k=5):
    """
    Retrieve documents from a vector database based on a query using maximal marginal relevance search, while filtering by a specific party.

    Arguments:
    - db: vector database
    - query: query string
    - party: party name (one of: "cdu", "spd", "gruene", "linke", "fdp", "afd")
    - k: number of documents to retrieve (default: 5)

    Returns:
    - docs: list of documents
    """

    docs = db.database.max_marginal_relevance_search(
        query, k=k, fetch_k=5, filter={"party": party}
    )
    return docs


# Deprecated
def build_context(self, query, k=5):

    docs = self.get_documents_for_all_parties(query, k=k)

    context = ""

    if self.source_type == "manifestos":
        context += "Ausschnitte aus den Wahlprogrammen zur Europawahl 2024:\n"
        source_description = "dem Wahlprogramm zur Europawahl 2024"
    elif self.source_type == "debates":
        context += "Ausschnitte aus vergangenen Reden im Europaparlament im Zeitraum 2019-2024:\n\n"
        source_description = "vergangenen Reden im Europaparlament"

    # Turn the dictionary of lists into a single (flat) list
    docs = [doc for party_docs in docs.values() for doc in party_docs]

    for doc in docs:
        context += f"Ausschnitt aus {source_description} "
        context += (
            f"von der {rename_party(doc.metadata['party'], 'anonymize').upper()}:\n"
        )
        context += f"{doc.page_content}\n\n"

    return context


def build_context_for_party(db, query, party, k=5):
    """
    Generate the "context" string for the prompt based on the documents retrieved for a specific party.

    Arguments:
    - db: vector database
    - query: query string
    - party: party name (one of: "cdu", "spd", "gruene", "linke", "fdp", "afd")
    """

    context_docs = get_documents_for_party(db, query, party, k=k)

    if db.source_type == "manifestos":
        context_header = "Ausschnitte aus den Wahlprogrammen zur Europawahl 2024:\n"
    elif db.source_type == "debates":
        context_header = "Ausschnitte aus vergangenen Reden im Europaparlament im Zeitraum 2019-2024:\n\n"

    context_content = "\n\n".join([doc.page_content for doc in context_docs])

    context_party = f"""
    {context_header}

    {context_content}
    """

    return context_party


# Deprecated
def generate_chain_all_in_one(
    dbs: list,
    llm=None,
    output_parser="json",
    temperature=0.0,
    k=5,
    return_context=False,
    language="Deutsch",
):
    """
    Generates a langchain: Change this code to change the chain!

    arguments:
    - dbs (list): list of databases
    - llm: language model to use (default: gpt-3.5-turbo)
    - output_parser: "json" or "str" (default: "json")
    - temperature: temperature for language model (default: 0.0)
    - k: number of documents to retrieve from each database (default: 5)
    - return context (boolean): If true, return dictionary that includes questions and context
    """

    if llm == None:
        llm = ChatOpenAI(
            model_name="gpt-3.5-turbo", max_tokens=2000, temperature=temperature
        )

    prompt_template = f"""   
    Beantworte die unten folgende FRAGE DES NUTZERS, indem du die politischen Positionen der im KONTEXT genannten Parteien zusammenfasst.
    Der KONTEXT umfasst Ausschnitte aus Debatten im EU-Parlament und der EU-Wahlprogramme für 2024. 
    Deine Antwort soll ausschließlich die Informationen aus dem genannten KONTEXT beinhalten.
    Mach deutlich, dass die Antwort den subjektiven Position der Parteien entspricht und distanziere dich falls nötig davon (z.B. mit wörtlicher Rede oder Konjunktiven).
    Gib die Antwort auf {language}.

    KONTEXT:
    {{context}}

    Sollte für eine Partei der oben genannte KONTEXT keine klare Antwort auf die unten genannte FRAGE DES NUTZERS zulassen, gib für diese Partei bitte folgende Rückmeldung: "Es wurde keine passende Antwort in den verfügbaren Daten gefunden."
    Andernfalls gib wie oben beschrieben eine Zusammenfassung der Positionen der Parteien wieder, um die nun folgende FRAGE DES NUTZERS zu beantworten:

    FRAGE DES NUTZERS: 
    {{question}}
    """
    # select output parser
    if output_parser == "json":
        output_parser = JsonOutputParser(pydantic_object=PartySummaries)
        prompt_template += "\n\n{format_instructions}\n"
        question_prompt = PromptTemplate(
            template=prompt_template,
            input_variables=["question", "context"],
            partial_variables={
                "format_instructions": output_parser.get_format_instructions()
            },
        )

    elif output_parser == "str":
        output_parser = StrOutputParser()
        question_prompt = PromptTemplate.from_template(prompt_template)

    else:
        raise ValueError("output_parser must be 'json' or 'str'")

    if return_context:
        # Create chain that returns context
        prompting_chain = RunnablePassthrough() | question_prompt | llm | output_parser

        # Returns a dict of question, context, and answer
        full_chain = {"question": RunnablePassthrough()} | RunnableParallel(
            {
                "question": lambda x: x["question"],
                "context": lambda x: "\n\n".join(
                    [db.build_context(query=x["question"], k=k) for db in dbs]
                ),
                "docs": lambda x: {
                    db.source_type: db.get_documents_for_each_party(
                        query=x["question"], k=k
                    )
                    for db in dbs
                },
            }
        ).assign(answer=prompting_chain)

    else:
        # Create chain without context return
        input_chain = {"question": RunnablePassthrough()} | RunnableParallel(
            {
                "question": lambda x: x["question"],
                "context": lambda x: "\n\n".join(
                    [db.build_context(query=x["question"], k=k) for db in dbs]
                ),
            }
        )

        # Returns a dict of question and answer
        full_chain = RunnableParallel(
            question=RunnablePassthrough(),
            answer=input_chain | question_prompt | llm | output_parser,
        )

    return full_chain


def generate_chain(
    dbs: list,
    llm=None,
    output_parser="json",
    temperature=0.0,
    k=5,
    language="Deutsch",
):
    """
    Generates a langchain: Change this code to change the chain!

    arguments:
    - dbs (list): list of databases
    - llm: language model to use (default: gpt-3.5-turbo)
    - output_parser: "json" or "str" (default: "json")
    - temperature: temperature for language model (default: 0.0)
    - k: number of documents to retrieve from each database (default: 5)
    - return context (boolean): If true, return dictionary that includes questions and context
    """

    if llm == None:
        llm = ChatOpenAI(
            model_name="gpt-3.5-turbo", max_tokens=300, temperature=temperature
        )

    prompt_template = f"""   
Beantworte die unten folgende FRAGE DES NUTZERS, indem du die politischen Positionen der Partei im unten angegebenen KONTEXT zusammenfasst.
Der KONTEXT umfasst Ausschnitte aus Redebeiträgen im EU-Parlament und aus dem EU-Wahlprogramm für 2024 für die Partei. 
Deine Antwort soll ausschließlich die Informationen aus dem genannten KONTEXT beinhalten.
Verwende in deiner Antwort NICHT den Namen der Partei, sondern beziehe dich auf die Partei ausschließlich mit "die Partei".
Sollte der KONTEXT keine Antwort auf die FRAGE DES NUTZERS zulassen, gib anstelle der Zusammenfassung NUR die folgende Rückmeldung: 
"Es wurde keine passende Antwort in den Quellen gefunden."
Gib die Antwort auf {language}.

KONTEXT:
{{context}}


FRAGE DES NUTZERS: 
{{question}}
    """

    output_parser = StrOutputParser()
    question_prompt = PromptTemplate.from_template(prompt_template)

    party_chains = {}
    parties = ["afd", "cdu", "fdp", "gruene", "linke", "spd"]

    # Generate separate chain for each party
    for party in parties:
        # Here you define your context builder logic
        retrieval_chain = RunnableParallel(
            {
                "question": lambda x: x["question"],
                "context": lambda x, party=party: "\n\n".join(
                    build_context_for_party(db, query=x["question"], party=party, k=k)
                    for db in dbs
                ),
                "docs": lambda x, party=party: {
                    db.source_type: get_documents_for_party(
                        db, query=x["question"], party=party, k=k
                    )
                    for db in dbs
                },
            }
        )

        llm_chain = RunnablePassthrough() | question_prompt | llm | output_parser

        party_chain = {"question": RunnablePassthrough()} | retrieval_chain.assign(
            answer=llm_chain
        )

        party_chains[party] = party_chain

    # Now we build the final chain: party chains run in parallel
    chain = RunnablePassthrough() | RunnableParallel(party_chains)

    return chain


if __name__ == "__main__":

    embedding_model = OpenAIEmbeddings(model="text-embedding-3-large")

    embedding_name = "openai"
    DATABASE_DIR = f"data/manifestos/chroma/{embedding_name}/"
    DATA_PATH = "data/manifestos/01_pdf_originals"

    db_manifestos = VectorDatabase(
        embedding_model=embedding_model,
        source_type="manifestos",
        database_directory=DATABASE_DIR,
        data_path=DATA_PATH,
        loader="pdf",
        reload=True,
    )

    chain, party_chains = generate_chain(
        [db_manifestos],
        k=1,
    )

    response = chain.invoke("Was sagen die Parteien zum Verhältnis zu Russland?")
    print(response["cdu"]["docs"])
    print()
    print(response["spd"]["docs"])
