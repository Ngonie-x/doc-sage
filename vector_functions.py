import os
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
from langchain_text_splitters import CharacterTextSplitter
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_community.document_loaders import (
    TextLoader,
    CSVLoader,
    PyPDFLoader,
    Docx2txtLoader,
    UnstructuredHTMLLoader,
    UnstructuredMarkdownLoader,
)


llm = ChatOpenAI(model="gpt-4o-mini")

embeddings = OpenAIEmbeddings()

text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)


def load_document(file_path: str) -> list[Document]:
    """
    Load a document from a file path.
    Supports .txt, .pdf, .docx, .csv, .html, and .md files.

    Args:
    file_path (str): Path to the document file.

    Returns:
    list[Document]: A list of Document objects.

    Raises:
    ValueError: If the file type is not supported.
    """
    _, file_extension = os.path.splitext(file_path)

    if file_extension == ".txt":
        loader = TextLoader(file_path)
    elif file_extension == ".pdf":
        loader = PyPDFLoader(file_path)
    elif file_extension == ".docx":
        loader = Docx2txtLoader(file_path)
    elif file_extension == ".csv":
        loader = CSVLoader(file_path)
    elif file_extension == ".html":
        loader = UnstructuredHTMLLoader(file_path)
    elif file_extension == ".md":
        loader = UnstructuredMarkdownLoader(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_extension}")

    return loader.load()


def create_collection(collection_name, documents):
    """
    Create a new Chroma collection from the given documents.

    Args:
    collection_name (str): The name of the collection to create.
    documents (list): A list of documents to add to the collection.

    Returns:
    None

    This function splits the documents into texts, creates a new Chroma collection,
    and persists it to disk.
    """
    # Split the documents into smaller text chunks
    texts = text_splitter.split_documents(documents)
    persist_directory = "./persist"

    # Create a new Chroma collection from the text chunks
    vectordb = Chroma.from_documents(
        documents=texts,
        embedding=embeddings,
        persist_directory=persist_directory,
        collection_name=collection_name,
    )

    # Save the collection to disk
    vectordb.persist()


def load_collection(collection_name):
    """
    Load an existing Chroma collection.

    Args:
    collection_name (str): The name of the collection to load.

    Returns:
    Chroma: The loaded Chroma collection.

    This function loads a previously created Chroma collection from disk.
    """
    persist_directory = "./persist"
    # Load the Chroma collection from the specified directory
    vectordb = Chroma(
        persist_directory=persist_directory,
        embedding_function=embeddings,
        collection_name=collection_name,
    )

    return vectordb


def load_retriever(collection_name, search_type: str = "similarity", k: int = 5):
    """
    Create a retriever from a Chroma collection.

    Args:
    collection_name (str): The name of the collection to use.
    search_type (str): The type of search to perform. Defaults to "similarity".
    k (int): The number of results to return. Defaults to 5.

    Returns:
    Retriever: A retriever object that can be used to query the collection.

    This function loads a Chroma collection and creates a retriever from it,
    which can be used to perform searches on the collection.
    """
    # Load the Chroma collection
    vectordb = load_collection(collection_name)
    # Create a retriever from the collection with specified search parameters
    retriever = vectordb.as_retriever(search_type=search_type, search_kwargs={"k": k})
    return retriever


def ask_question(retriever, question: str):
    """
    Ask a question and get an answer based on the provided context.

    Args:
        retriever: A retriever object to fetch relevant context.
        question (str): The question to be answered.

    Returns:
        str: The answer to the question based on the retrieved context.
    """
    # Define the message template for the prompt
    message = """
    Answer this question using the provided context only.

    {question}

    Context:
    {context}
    """

    # Create a chat prompt template from the message
    prompt = ChatPromptTemplate.from_messages([("human", message)])

    # Create a RAG (Retrieval-Augmented Generation) chain
    # This chain retrieves context, passes through the question,
    # formats the prompt, and generates an answer using the language model
    rag_chain = {"context": retriever, "question": RunnablePassthrough()} | prompt | llm

    # Invoke the RAG chain with the question and return the generated content
    return rag_chain.invoke({"question": question}).content


def add_documents_to_collection(vectordb, documents):
    """
    Add documents to the vector database collection.

    Args:
        vectordb: The vector database object to add documents to.
        documents: A list of documents to be added to the collection.

    This function splits the documents into smaller chunks, adds them to the
    vector database, and persists the changes.
    """

    # Split the documents into smaller text chunks
    texts = text_splitter.split_documents(documents)

    # Add the text chunks to the vector database
    vectordb.add_documents(texts)

    # Persist the changes to ensure they are saved
    vectordb.persist()
