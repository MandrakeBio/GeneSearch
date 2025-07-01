import openai
from dotenv import load_dotenv
from agents.web_search.models import (
    WebResearchAgentModel,
    WebResearchResult,
    UpNextQueries
)
from agents.web_search.prompts import (
    RESEARCH_PROMPT,
    MAKE_AGENT_QUERY_PROMPT,
    EXTRACT_FROM_RESEARCH_PROMPT
)

load_dotenv()

class WebResearchAgent:
    def __init__(self) -> None:
        print("Initializing WebResearchAgent...")
        self.client = openai.OpenAI()

    def get_raw_research_dump(self, query: str):
        print(f"Getting raw research dump.")
        result = self.client.chat.completions.create(
            model="gpt-4o-search-preview",
            web_search_options={
                "search_context_size": "high"
            },
            messages=[
                {"role": "system", "content": RESEARCH_PROMPT},
                {"role": "user", "content": query}
            ]
        )
        content = result.choices[0].message.content
        print(f"Received raw research dump of length: {len(content)}")
        return content
    
    def extract_from_research(self, query: str, research_dump: str):
        print(f"Extracting structured data from research dump")
        prompt = f""""
        Here is the user query: {query} and the research dump from the model:
        {research_dump} 
        """
        completions = self.client.beta.chat.completions.parse(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": EXTRACT_FROM_RESEARCH_PROMPT},
                {"role": "user", "content": prompt}
            ],
            response_format=WebResearchResult
        )
        result = completions.choices[0].message.parsed
        print(f"Extracted {len(result.search_result)} search results")
        return result
    
    def find_queries_to_pass(self, query: str, research_dump: str):
        print(f"Finding follow-up queries.")
        prompt = f""""
        Here is the user query: {query} and the research dump from the model:
        {research_dump} 
        """
        completions = self.client.beta.chat.completions.parse(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": MAKE_AGENT_QUERY_PROMPT},
                {"role": "user", "content": prompt}
            ],
            response_format=UpNextQueries
        )
        result = completions.choices[0].message.parsed
        print(f"Generated {len(result.queries)} follow-up queries")
        return result
    
    def search(self, query: str) -> WebResearchAgentModel:
        print(f"\nStarting web research")
        raw_result = self.get_raw_research_dump(query)
        research_paper = self.extract_from_research(query, raw_result)
        upnext_queries = self.find_queries_to_pass(query, raw_result)
        
        result = WebResearchAgentModel(
            query=query,
            raw_result=raw_result,
            research_paper=research_paper,
            upnext_queries=upnext_queries.queries
        )
        print(f"Completed web research with {len(result.research_paper.search_result)} results and {len(result.upnext_queries)} follow-up queries")
        return result
