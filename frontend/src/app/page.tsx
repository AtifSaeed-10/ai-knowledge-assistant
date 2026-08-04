"use client";

import React from "react";
import { AppLayout } from "@/components/layout/AppLayout";
import { DocumentUploader } from "@/components/documents/DocumentUploader";
import { ChatContainer } from "@/components/chat/ChatContainer";
import { useDocumentStore } from "@/store/useDocumentStore";
import { Logo } from "@/components/ui/Logo";

export default function WorkspacePage() {
  const documents = useDocumentStore((state) => state.documents);

  const hasDocuments = documents.length > 0;
  const hasReady = documents.some((doc) => doc.status === "ready");

  return (
    <AppLayout>

      {/* STATE 1: EMPTY */}
      {!hasDocuments && (
        <div
          className="
            relative
            flex
            flex-col
            items-center
            justify-center
            h-full
            min-h-[60vh]
            overflow-hidden
          "
        >

          {/* Premium Ambient Olive Glow */}
          <div
            className="
              absolute
              top-1/2
              left-1/2
              -translate-x-1/2
              -translate-y-1/2
              flex
              items-center
              justify-center
              pointer-events-none
            "
          >
            <div
              className="
              w-[28rem]
              h-[28rem]
              rounded-full
              bg-[#87AB72]/25
              blur-[90px]
              animate-ambient-glow
              "
            />
          </div>



          {/* Hero Content */}
          <div
            className="
              relative
              z-10
              max-w-2xl
              w-full
              text-center
              space-y-8
              animate-in
              fade-in
              slide-in-from-bottom-3
              duration-700
            "
          >


            {/* Logo + Welcome */}
            <div
              className="
                flex
                flex-col
                items-center
                space-y-5
              "
            >

              {/* Logo */}
              <div
                className="
                  flex
                  items-center
                  justify-center
                  w-20
                  h-20
                  rounded-3xl
                  bg-white/90
                  backdrop-blur-sm
                  border
                  border-[#4A5D23]/10
                  shadow-md
                  animate-float
                "
              >
                <Logo className="w-10 h-10 text-[#4A5D23]" />
              </div>



              {/* Heading */}
              <div className="space-y-3">

                <h1
                  className="
                    text-4xl
                    md:text-5xl
                    font-semibold
                    tracking-tight
                    text-[#1C241F]
                  "
                >
                  Welcome to DocuSage
                </h1>


                <p
                  className="
                    text-base
                    md:text-lg
                    text-[#6F7B6B]
                  "
                >
                  Upload documents to train your AI assistant.
                </p>

              </div>

            </div>



            {/* Existing uploader untouched */}
            <div
              className="
                bg-white/90
                backdrop-blur-sm
                rounded-2xl
                border
                border-[#EBEFEA]
                shadow-lg
                p-2
                sm:p-6
              "
            >
              <DocumentUploader />
            </div>


          </div>


        </div>
      )}



      {/* STATE 2: PROCESSING */}
      {hasDocuments && !hasReady && (
        <div
          className="
            flex
            flex-col
            items-center
            justify-center
            h-full
            min-h-[60vh]
          "
        >

          <div
            className="
              max-w-md
              w-full
              space-y-6
              text-center
              animate-in
              fade-in
              duration-500
            "
          >

            <div
              className="
                p-8
                bg-white
                rounded-2xl
                shadow-sm
                border
                border-gray-100
              "
            >

              <div
                className="
                  w-12
                  h-12
                  border-4
                  border-[#4A5D23]
                  border-t-transparent
                  rounded-full
                  animate-spin
                  mx-auto
                  mb-4
                "
              />

              <h2
                className="
                  text-xl
                  font-bold
                  text-gray-900
                "
              >
                Processing Documents
              </h2>


              <p
                className="
                  text-sm
                  text-gray-500
                  mt-2
                "
              >
                Check the sidebar for extraction and indexing progress.
              </p>


            </div>

          </div>

        </div>
      )}




      {/* STATE 3: READY */}
      {hasDocuments && hasReady && (
        <div
          className="
            h-full
            w-full
            animate-in
            fade-in
            duration-300
          "
        >
          <ChatContainer />
        </div>
      )}


    </AppLayout>
  );
}