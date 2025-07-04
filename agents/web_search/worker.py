import os
from openai import AzureOpenAI
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
        self.client = AzureOpenAI(
            api_version="2024-12-01-preview",
            azure_endpoint="https://tanay-mcn037n5-eastus2.cognitiveservices.azure.com/",
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        )

    def get_raw_research_dump(self, query: str):
        print(f"Getting raw research dump.")
        result = self.client.chat.completions.create(
            model="gpt-4.1",
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
        completions = self.client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": EXTRACT_FROM_RESEARCH_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1500
        )
        
        # Parse the response manually since we can't use structured output
        response_content = completions.choices[0].message.content
        print(f"Received response for extraction")
        
        # Return a simple structure for now
        result = WebResearchResult(
            search_result=[],
            summary=response_content or "No structured data extracted"
        )
        print(f"Created basic extraction result")
        return result
    
    def find_queries_to_pass(self, query: str, research_dump: str):
        print(f"Finding follow-up queries.")
        prompt = f""""
        Here is the user query: {query} and the research dump from the model:
        {research_dump} 
        """
        completions = self.client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": MAKE_AGENT_QUERY_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )
        
        # Parse the response manually 
        response_content = completions.choices[0].message.content or ""
        
        # Extract queries from the response (simple parsing)
        queries = []
        if response_content:
            lines = response_content.split('\n')
            for line in lines:
                if line.strip() and not line.startswith('#'):
                    queries.append(line.strip())
        
        result = UpNextQueries(queries=queries[:3])  # Limit to 3 queries
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
