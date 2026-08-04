"use client";


import React from "react";

import {
  useChatStore
} from "@/store/useChatStore";

import {
  useDocumentStore
} from "@/store/useDocumentStore";


import {
  MessageList
} from "./MessageList";


import {
  ChatInput
} from "./ChatInput";


import {
  CitationDrawer
} from "./CitationDrawer";


import {
  Trash2,
  MessageSquare
} from "lucide-react";



export function ChatContainer() {


  const {
    messages,
    isLoading,
    sendMessage,
    clearMessages
  } = useChatStore();



  const {
    documents
  } = useDocumentStore();



  const readyDocuments =
    documents.filter(
      (doc) =>
        doc.status === "ready"
    );


  const hasReadyDocs =
    readyDocuments.length > 0;



  const handleSend = (
    content: string
  ) => {

    sendMessage(content);

  };



  return (

    <div
      className="
      flex flex-col
      h-[calc(100vh-7.5rem)]
      bg-white
      rounded-2xl
      shadow-sm
      border
      border-gray-100
      overflow-hidden
      relative
      "
    >


      {/* Chat Header */}

      <div
        className="
        px-6 py-3.5
        border-b
        border-gray-100
        flex
        items-center
        justify-between
        bg-white
        "
      >


        <div
          className="
          flex items-center gap-3
          "
        >

          <div
            className="
            p-2
            bg-[#F6F7F4]
            rounded-lg
            text-[#4A5D23]
            "
          >

            <MessageSquare
              className="w-4 h-4"
            />

          </div>



          <div>

            <h3
              className="
              font-semibold
              text-gray-900
              text-sm
              "
            >
              Assistant Chat
            </h3>


            <p
              className="
              text-xs
              text-gray-500
              "
            >

              {
                hasReadyDocs
                ? `Querying across ${readyDocuments.length} ready document(s)`
                : "Upload a document to enable querying"
              }

            </p>


          </div>


        </div>




        {
          messages.length > 0 && (

            <button
              onClick={clearMessages}
              className="
              flex items-center gap-1.5
              px-3 py-1.5
              text-xs
              text-gray-500
              hover:text-red-600
              hover:bg-red-50
              rounded-lg
              transition-colors
              "
            >

              <Trash2
                className="w-3.5 h-3.5"
              />

              <span
                className="hidden sm:inline"
              >
                Clear Chat
              </span>


            </button>

          )
        }



      </div>





      {/* Messages Area */}

      <div
        className="
        flex-1
        overflow-hidden
        flex
        flex-col
        bg-[#F6F7F4]/40
        "
      >

        <MessageList

          messages={messages}

          isLoading={isLoading}

          onSelectPrompt={handleSend}

        />


      </div>





      {/* Input */}

      <div
        className="
        p-4
        bg-white
        border-t
        border-gray-100
        "
      >


        <ChatInput

          onSend={handleSend}

          isLoading={isLoading}

          disabled={!hasReadyDocs}

        />


      </div>





      {/* Citation Drawer */}

      <CitationDrawer />


    </div>

  );

}