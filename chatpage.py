import streamlit as st
import os
import requests
from bs4 import BeautifulSoup
from langchain_core.documents import Document
import math
from db import (
    read_chat,
    create_chat,
    list_chats,
    delete_chat,
    create_message,
    get_messages,
    delete_messages,
    create_source,
    list_sources,
    delete_source,
)
from vector_functions import (
    load_document,
    create_collection,
    load_retriever,
    ask_question,
    add_documents_to_collection,
    load_collection,
)


def chats_page():
    st.markdown(
        "<h1 style='text-align: center;'>StudySage🧙‍♂️</h1>", unsafe_allow_html=True
    )

    with st.container(border=True):
        col1, col2 = st.columns([0.8, 0.2])

        with col1:
            chat_title = st.text_input(
                "Chat Title", placeholder="Enter Chat Title", key="chat_title"
            )

        with col2:
            st.markdown("<br>", unsafe_allow_html=True)  # Add vertical space
            if st.button("Create Chat", type="primary"):
                if chat_title:
                    chat_id = create_chat(chat_title)
                    st.success(f"Created new chat: {chat_title}")
                    st.query_params.from_dict({"chat_id": chat_id})
                    st.rerun()
                else:
                    st.warning("Please enter a chat title")

    with st.container(border=True):
        st.subheader("Previous Chats")

        # get previous chats from db
        previous_chats = list_chats()

        # Pagination settings
        chats_per_page = 5
        total_pages = math.ceil(len(previous_chats) / chats_per_page)

        # Get current page from session state
        if "current_page" not in st.session_state:
            st.session_state.current_page = 1

        # Calculate start and end indices for the current page
        start_idx = (st.session_state.current_page - 1) * chats_per_page
        end_idx = start_idx + chats_per_page

        # Display chats for the current page
        for chat in previous_chats[start_idx:end_idx]:
            chat_id, chat_title = chat[0], chat[1]
            with st.container(border=True):
                col1, col2, col3 = st.columns([0.6, 0.2, 0.2])
                with col1:
                    st.write(chat_title)
                with col2:
                    if st.button("Open", key=f"open_{chat_id}"):
                        st.query_params.from_dict({"chat_id": chat_id})
                        st.rerun()
                with col3:
                    if st.button("Delete", key=f"delete_{chat_id}"):
                        delete_chat(chat_id)
                        st.success(f"Deleted chat: {chat_title}")
                        st.rerun()

        # Pagination controls
        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            if st.button("Previous") and st.session_state.current_page > 1:
                st.session_state.current_page -= 1
                st.rerun()
        with col2:
            st.write(f"Page {st.session_state.current_page} of {total_pages}")
        with col3:
            if st.button("Next") and st.session_state.current_page < total_pages:
                st.session_state.current_page += 1
                st.rerun()


def chat_page(chat_id):
    chat = read_chat(chat_id)
    if not chat:
        st.error("Chat not found")
        return

    st.markdown(
        f"<h1 style='text-align: center;'>{chat[1]}</h1>", unsafe_allow_html=True
    )

    # Retrieve messages from DB
    messages = get_messages(chat_id)

    # Display messages
    if messages:
        for sender, content in messages:
            if sender == "user":
                with st.chat_message("user"):
                    st.markdown(content)
            elif sender == "ai":
                with st.chat_message("assistant"):
                    st.markdown(content)
    else:
        st.write("No messages yet. Start the conversation!")

    # Add a text input for new messages
    prompt = st.chat_input("Type your message here...")
    if prompt:
        # Save user message
        create_message(chat_id, "user", prompt)
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        # Get AI response

        # Load retriever for the chat context
        collection_name = f"chat_{chat_id}"
        if os.path.exists(f"./persist/{collection_name}"):
            retriever = load_retriever(collection_name=collection_name)
        else:
            retriever = None

        # Ask question using the retriever
        response = (
            ask_question(retriever, prompt)
            if retriever
            else "I need some context to answer that question."
        )

        # Save AI response
        create_message(chat_id, "ai", response)
        # Display AI response
        with st.chat_message("assistant"):
            st.markdown(response)
        st.rerun()

    # Sidebar for context
    with st.sidebar:
        # Button to return to the main chats page
        if st.button("Back to Chats"):
            st.query_params.clear()
            st.rerun()

        # Documents Section
        st.subheader("Documents")
        # Display list of documents
        documents = list_sources(chat_id, source_type="document")
        if documents:
            for doc in documents:
                doc_id = doc[0]
                doc_name = doc[1]
                col1, col2 = st.columns([0.8, 0.2])
                with col1:
                    st.write(doc_name)
                with col2:
                    if st.button("Delete", key=f"delete_doc_{doc_id}"):
                        delete_source(doc_id)
                        st.success(f"Deleted document: {doc_name}")
                        st.rerun()
        else:
            st.write("No documents uploaded.")

        # Upload new document
        uploaded_file = st.file_uploader("Upload Document", key="file_uploader")
        if uploaded_file:
            # Save document content to database
            with st.spinner("Processing document..."):
                temp_dir = "temp_files"
                os.makedirs(temp_dir, exist_ok=True)
                temp_file_path = os.path.join(temp_dir, uploaded_file.name)
                with open(temp_file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                # Load document
                documents = load_document(temp_file_path)
                # Create or update collection for this chat
                collection_name = f"chat_{chat_id}"
                if not os.path.exists(f"./persist/{collection_name}"):
                    create_collection(collection_name, documents)
                else:
                    vectordb = load_collection(collection_name)
                    add_documents_to_collection(vectordb, documents)
                # Save source to database
                create_source(uploaded_file.name, "", chat_id, source_type="document")
                # Remove temp file
                os.remove(temp_file_path)
            st.success(f"Uploaded document: {uploaded_file.name}")
            st.rerun()

        # Links Section
        st.subheader("Links")
        # Display list of links
        links = list_sources(chat_id, source_type="link")
        if links:
            for link in links:
                link_id = link[0]
                link_url = link[1]
                col1, col2 = st.columns([0.8, 0.2])
                with col1:
                    st.markdown(f"[{link_url}]({link_url})")
                with col2:
                    if st.button("Delete", key=f"delete_link_{link_id}"):
                        delete_source(link_id)
                        st.success(f"Deleted link: {link_url}")
                        st.rerun()
        else:
            st.write("No links added.")

        # Add new link
        new_link = st.text_input("Add a link", key="new_link")
        if st.button("Add Link"):
            if new_link:
                # Fetch content from the link
                try:
                    response = requests.get(new_link)
                    soup = BeautifulSoup(response.text, "html.parser")
                    link_content = soup.get_text(separator="\n")

                    # Save link content to vector store
                    documents = [
                        Document(
                            page_content=link_content, metadata={"source": new_link}
                        )
                    ]
                    collection_name = f"chat_{chat_id}"
                    if not os.path.exists(f"./persist/{collection_name}"):
                        create_collection(collection_name, documents)
                    else:
                        vectordb = load_collection(collection_name)
                        add_documents_to_collection(vectordb, documents)

                    # Save link to database
                    create_source(new_link, "", chat_id, source_type="link")
                    st.success(f"Added link: {new_link}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to fetch content from the link: {e}")
            else:
                st.warning("Please enter a link")


def main():
    query_params = st.query_params
    if "chat_id" in query_params:
        chat_id = query_params["chat_id"][0]
        chat_page(chat_id)
    else:
        chats_page()


if __name__ == "__main__":
    main()