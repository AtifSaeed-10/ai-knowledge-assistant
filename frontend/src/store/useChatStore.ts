import { create } from 'zustand';
import { Message, Citation } from '@/types';
import { chatApi } from '@/lib/api/chat';
import { useDocumentStore } from './useDocumentStore';


const SESSION_CONVERSATION_ID =
  `conv-${Math.random().toString(36).substring(2, 9)}`;



interface ChatState {

  messages: Message[];

  isLoading: boolean;

  activeCitation: Citation | null;

  setActiveCitation:
    (citation: Citation | null) => void;

  sendMessage:
    (content: string) => Promise<void>;

  clearMessages:
    () => void;

}



export const useChatStore = create<ChatState>((set) => ({

  messages: [],

  isLoading: false,

  activeCitation: null,



  setActiveCitation:
    (citation) =>
      set({
        activeCitation: citation
      }),




  sendMessage:
    async (content: string) => {



      // Close citation drawer
      set({
        activeCitation: null
      });



      const userMessage: Message = {

        id: `user-${Date.now()}`,

        role: "user",

        content,

        timestamp: new Date(),

      };




      const assistantId =
        `assistant-${Date.now()}`;



      const emptyAssistantMessage: Message = {

        id: assistantId,

        role: "assistant",

        content: "",

        timestamp: new Date(),

        citations: [],

      };





      set((state) => ({

        messages: [

          ...state.messages,

          userMessage,

          emptyAssistantMessage

        ],

        isLoading: true,

      }));






      try {



        const readyDocuments =
          useDocumentStore
            .getState()
            .documents
            .filter(
              (doc) =>
                doc.status === "ready"
            );



        if (readyDocuments.length === 0) {

          throw new Error(
            "No ready documents available."
          );

        }



        const documentIds =
          readyDocuments.map(
            doc => doc.id
          );





        await chatApi.streamMessage(

          content,

          documentIds,

          SESSION_CONVERSATION_ID,

          (token) => {



            set((state) => ({


              messages:
                state.messages.map(
                  (msg) =>

                    msg.id === assistantId

                    ?

                    {
                      ...msg,

                      content:
                        msg.content + token
                    }

                    :

                    msg

                )

            }));



          },



          (citations) => {



            set((state) => ({


              messages:
                state.messages.map(
                  (msg) =>


                    msg.id === assistantId


                    ?

                    {
                      ...msg,

                      citations

                    }


                    :

                    msg

                ),


              isLoading:false


            }));



          }



        );




      }

      catch(error) {



        console.error(
          "Streaming failed:",
          error
        );



        set((state)=>({


          messages:
            state.messages.map(
              msg =>


              msg.id === assistantId

              ?

              {

                ...msg,

                content:
                  "Sorry, I encountered an error communicating with the server."

              }


              :

              msg

            ),


          isLoading:false


        }));


      }



    },





  clearMessages:

    () =>

      set({

        messages: [],

        activeCitation:null

      }),



}));