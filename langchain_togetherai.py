from langchain.memory import ConversationBufferMemory
from langchain import LLMChain, PromptTemplate
from TogetherLLM import TogetherLLM
import streamlit as st
import textwrap
from query_results import search_results
from pprint import pprint
import requests
from ExtractImage import Extract_Image
from PIL import Image
import requests
from io import BytesIO

instruction = "Chat History:\n\n{chat_history} \n\nHuman: {user_input}\n\n Assistant:"
system_prompt = """
Your name is FashionKart, a fashion store outfit generator chatbot.
You are here to help users create stylish outfit ideas for various occasions.
You are here to provide users with fashionable suggestions.
You should give a response within 100 words.
Start the conversation by introducing yourself, greeting the user and asking for their name.
Then ask the user for the outfit details, such as occasion, style, etc.
Give the user a suggestion, and do not add any summary in this response itself.
If the user says that they like the suggestion, then ask whether the user would like to add anything else to the outfit.
If the user mentions something they would like to add, add it to the list, and ask them again if they would like to add anything else.
You must ensure that in the final outfit, either you can suggest both top and bottom, or you can suggest a onepiece.
If the user says no, then give a concise summary of the whole outfit including any accesories or footwear as a JSON object or dictionary in the format shown below.
{{
  'occasion': ['birthday', 'party'],
    'top': ['t-shirt', 'crop-top'],
    'bottom': ['jeans', 'shorts'],
    'footwear': ['sneakers'],
    'coverall': ['jackets'],
    'onepiece': ['dress', 'gown'],
    'accessories': [] }}   
In the final JSON object or dictionary, two categories cannot have the same item. Also if onepiece is present, then top and bottom must be empty. Similarly, if top and bottom are present, then onepiece must be empty.
You cannot have any key outside of the ones given in the example above. You have to fit in every item as a value in one of the keys given above.
If the user says that they do not like a particular product, then return another suggestion as a JSON object described above., do not add anything the user does not ask or agree to explicitly. Change only the product that the user mentions they don't like.
"""

B_INST, E_INST = "[INST]", "[/INST]"
B_SYS, E_SYS = "<<SYS>>\n", "\n<</SYS>>\n\n"
# DEFAULT_SYSTEM_PROMPT = """\
# You are a helpful, respectful and honest assistant. Always answer as helpfully as possible, while being safe. Your answers should not include any harmful, unethical, racist, sexist, toxic, dangerous, or illegal content. Please ensure that your responses are socially unbiased and positive in nature.

# If a question does not make any sense, or is not factually coherent, explain why instead of answering something not correct. If you don't know the answer to a question, please don't share false information."""

image = Extract_Image()

def get_prompt(instruction, new_system_prompt = system_prompt ):
    SYSTEM_PROMPT = B_SYS + new_system_prompt + E_SYS
    prompt_template =  B_INST + SYSTEM_PROMPT + instruction + E_INST
    return prompt_template

def cut_off_text(text, prompt):
    cutoff_phrase = prompt
    index = text.find(cutoff_phrase)
    if index != -1:
        return text[:index]
    else:
        return text

def remove_substring(string, substring):
    return string.replace(substring, "")


def parse_text(text):
        wrapped_text = textwrap.fill(text, width=100)
        print(wrapped_text +'\n\n')
        # return assistant_text

def parse_recommendations(result):
    with st.container():
        # st.markdown(f"**{result['name']}**")
        col1, col2 = st.columns(2)
        with col1:
            if result["image"]:
                st.image(result["image"], use_column_width=False)
            else:
                st.image('imagenotfound.png', use_column_width=True)
        with col2:
            st.markdown(f"**{result['name']}**")
            st.markdown(f"**Current Price:** {result['current_price']}")
            st.markdown(f"**Original Price:** {result['original_price']}")
            st.markdown(f"**Discounted:** {result['discounted']}")
            st.markdown(f"**Buy Now:** {result['share_url']}")


template = get_prompt(instruction, system_prompt)
prompt = PromptTemplate(
    input_variables=["chat_history", "user_input"], template=template
)

if "memory" not in st.session_state.keys():
    st.session_state.memory = ConversationBufferMemory(memory_key="chat_history")

if "llm" not in st.session_state.keys():
    st.session_state.llm = TogetherLLM(
        model= "togethercomputer/llama-2-70b-chat",
        temperature=0.1,
        max_tokens=512
    )

llm_chain = LLMChain(
    llm=st.session_state.llm,
    prompt=prompt,
    verbose=True,
    memory=st.session_state.memory,
)

st.title("FashionKart")

if "messages" not in st.session_state.keys():
    st.session_state.messages = [] 

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if "recommendation" in message:
            parse_recommendations(message["recommendation"])
        else:
            st.write(message["content"])

# React to user input
if prompt := st.chat_input("Type your message here...", key="user_input"):
    # Display user message in chat message container
    st.chat_message("user").markdown(prompt)
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})

    index = {"top": -1,"bottom": -1,"coverall": -1,"onepiece": -1, "accessories": -1, "footwear": -1}
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = llm_chain.predict(user_input=prompt)
            if response.find('{') == -1:
                # Display assistant response in chat message container
                
                st.markdown(response)
                # Add assistant response to chat history
                st.session_state.messages.append({"role": "assistant", "content": response})
            else:
                categories = response[response.find('{'):response.find('}')+1]
                gender = []
                name = str(llm_chain.predict(user_input="What is my name? Return only my name in one word and nothing else"))
                gender.append(str(llm_chain.predict(user_input="What do you think my gender is? The response has to be one word - either 'women' or 'men'")))
                if (gender[0].find('women')!=-1) or gender[0].find('woman')!= -1 or gender[0].find('female') != -1: 
                    gender[0] = "women"
                elif(gender[0].find('men')!=-1) or gender[0].find('man') != -1 or gender[0].find('male') != -1:
                    gender[0] = "men" 
            
                categories = eval(categories)
                search_results = search_results(categories, name[1:], gender)

                for category in search_results:
                    flag = 0
                    if len(search_results[category]) == 0:
                        continue
                    while flag == 0 and index[category] + 1 < len(search_results[category]):
                        index[category] += 1
                        top_product = search_results[category][index[category]]
                        # print(top_product)
                        string = '/'.join(top_product[2].split('/')[3:])
                        query_url = "https://flipkart-scraper-api.dvishal485.workers.dev/product/" + string
                        # print(query_url)
                        result = requests.get(query_url).json()
                        if 'name' in result:
                            print(gender, result['name'])
                            if gender[0] == "women" and result['name'].find("Women") != -1:
                                    flag = 1
                            elif gender[0] == "men" and result['name'].find("Women") == -1:
                                    print("take", result['name'], result['name'].find("Women"))
                                    flag = 1
                        else:
                            continue

                    print(category, result)
                    image.set_url(top_product[2])
                    img = image.get_image()
                    image_height = 10
                    result["image"] = img
                    parse_recommendations(result)
                    
                    st.session_state.messages.append({"role": "assistant", "content": response, "recommendation": result})
                

with st.sidebar:
    st.subheader("About")
    st.markdown(
        """
        This app is a demo for the FashionKart Outfit Generator ChatBot.
        The chatbot is powered by the LLaMA2-70B language model.

        """
    )
    st.button("Clear Chat History", on_click=lambda: st.session_state.clear())


        


    
