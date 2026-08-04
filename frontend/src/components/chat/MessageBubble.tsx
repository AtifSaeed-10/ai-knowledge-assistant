"use client";

import React from "react";
import { User } from "lucide-react";
import { Message } from "@/types";
import { SourceList } from "./SourceList";
import { Logo } from "@/components/ui/Logo";


interface MessageBubbleProps {
  message: Message;
}


export function MessageBubble({
  message,
}: MessageBubbleProps) {

  const isUser = message.role === "user";


  return (
    <div
      className={`flex gap-3 my-4 ${
        isUser ? "flex-row-reverse" : "flex-row"
      }`}
    >

      {/* Avatar */}
      <div
        className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 shadow-sm ${
          isUser
            ? "bg-gray-800 text-white"
            : "bg-[#4A5D23] text-white"
        }`}
      >

        {isUser ? (
          <User className="w-4 h-4" />
        ) : (
          <Logo className="w-5 h-5 text-white" />
        )}

      </div>



      {/* Message Content */}
      <div className="max-w-[82%] sm:max-w-[75%] space-y-2">


        {/* Message Bubble */}
        <div
          className={`px-4 py-3 rounded-2xl text-sm leading-relaxed shadow-sm ${
            isUser
              ? "bg-[#4A5D23] text-white rounded-tr-sm"
              : "bg-white text-gray-800 border border-gray-100 rounded-tl-sm"
          }`}
        >

          <div className="whitespace-pre-wrap">
            {message.content}
          </div>

        </div>



        {/* Citation Chips */}
        {!isUser &&
          message.citations &&
          message.citations.length > 0 && (

            <SourceList
              citations={message.citations}
            />

        )}



        {/* Timestamp */}
        <div
          className={`text-[10px] text-gray-400 px-1 ${
            isUser
              ? "text-right"
              : "text-left"
          }`}
        >

          {message.timestamp
            ? new Date(
                message.timestamp
              ).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              })
            : ""}

        </div>


      </div>

    </div>
  );
}