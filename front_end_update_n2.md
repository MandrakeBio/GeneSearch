# Frontend Update Guide - GeneSearch v2.0

## Overview

This document outlines the **minimal necessary frontend updates** to support the major backend changes in GeneSearch v2.0, including Azure OpenAI migration, multi-turn chat functionality, and general biological analysis capabilities.

## 🔄 Major Backend Changes

### 1. Azure OpenAI Migration
- **Model**: Changed from OpenAI to Azure OpenAI o4-mini
- **Configuration**: Hardcoded endpoint and deployment settings
- **API Compatibility**: Removed temperature parameters (not supported by o4-mini)

### 2. Multi-Turn Chat Functionality
- **New Endpoint**: `/chat` for conversational interactions
- **Conversation History**: Maintains context across multiple messages
- **Memory Management**: Keeps last 20 messages per conversation

### 3. General Biological Analysis
- **Scope Expansion**: From gene-specific to any biological question
- **Adaptive Analysis**: Domain-specific analysis based on question type
- **Flexible Output**: Handles genes, pathways, mechanisms, diseases, evolution

## 🎯 Minimal Frontend Updates Required

### 1. API Client Updates (REQUIRED)

#### Add Chat Endpoint Integration
```typescript
// Add these interfaces to your existing types
interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp?: string;
}

interface ChatRequest {
  message: string;
  conversation_id?: string;
  chat_history: ChatMessage[];
}

interface ChatResponse {
  response: string;
  conversation_id: string;
  chat_history: ChatMessage[];
  success: boolean;
}

// Add this function to your API client
const sendChatMessage = async (request: ChatRequest): Promise<ChatResponse> => {
  const response = await fetch('/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request)
  });
  return response.json();
};
```

### 2. Update Analysis Response Handling (REQUIRED)

#### Update Analysis Interfaces
```typescript
// Change this in your existing analysis interfaces
interface AnalysisResponse {
  ranked_entities: BiologicalEntity[]; // WAS: ranked_genes
  analysis_summary: string;
  sources_analyzed: SourcesSummary;
}

interface BiologicalEntity {
  entity_name: string; // WAS: gene_name
  priority_rank: number;
  evidence_summary: string;
  biological_hypothesis: string;
  confidence: 'High' | 'Medium' | 'Low';
  references: Reference[];
  hyperlinks: Record<string, string>;
  detailed_evidence: {
    statistical_associations: number; // WAS: gwas_associations
    literature_support: number;
    pathway_involvement: number;
  };
}
```

### 3. Add Chat Option to Existing Search (REQUIRED)

#### Update Search Form
```typescript
// Add 'chat' to your existing search type options
const searchTypes = ['combined', 'gene', 'web', 'chat']; // Add 'chat'

// Update your existing search handler
const handleSearch = async () => {
  if (searchType === 'chat') {
    // Handle chat search
    const response = await sendChatMessage({
      message: query,
      conversation_id: conversationId,
      chat_history: chatHistory
    });
    setChatHistory(response.chat_history);
    setConversationId(response.conversation_id);
  } else {
    // Handle traditional search (existing code)
    await performSearch(query, searchType, includeWeb, includeGene);
  }
};
```

### 4. Update Analysis Display (REQUIRED)

#### Update Analysis Component
```typescript
// Change this in your existing analysis display
{analysis.ranked_entities.map((entity, index) => ( // WAS: ranked_genes
  <div key={index} className="entity-card">
    <h3>{entity.entity_name}</h3> {/* WAS: gene_name */}
    <p><strong>Evidence:</strong> {entity.evidence_summary}</p>
    <p><strong>Biological Hypothesis:</strong> {entity.biological_hypothesis}</p>
    
    <div className="evidence-stats">
      <span>📊 {entity.detailed_evidence.statistical_associations} associations</span> {/* WAS: gwas_associations */}
      <span>📚 {entity.detailed_evidence.literature_support} publications</span>
      <span>🔄 {entity.detailed_evidence.pathway_involvement} pathways</span>
    </div>
  </div>
))}
```

### 5. Simple Chat Integration (OPTIONAL)

#### Basic Chat Component
```typescript
// Simple chat component that can be integrated into existing search
const SimpleChat = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string>('');
  const [inputMessage, setInputMessage] = useState('');

  const sendMessage = async () => {
    if (!inputMessage.trim()) return;
    
    const request: ChatRequest = {
      message: inputMessage,
      conversation_id: conversationId,
      chat_history: messages
    };

    try {
      const response = await sendChatMessage(request);
      setMessages(response.chat_history);
      setConversationId(response.conversation_id);
      setInputMessage('');
    } catch (error) {
      console.error('Chat error:', error);
    }
  };

  return (
    <div className="simple-chat">
      <div className="messages">
        {messages.map((msg, index) => (
          <div key={index} className={`message ${msg.role}`}>
            <div className="content">{msg.content}</div>
          </div>
        ))}
      </div>
      
      <div className="chat-input">
        <input
          value={inputMessage}
          onChange={(e) => setInputMessage(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
          placeholder="Ask a biological question..."
        />
        <button onClick={sendMessage}>Send</button>
      </div>
    </div>
  );
};
```

## 🎯 Summary of Required Changes

### **What's Actually Needed (Minimal Changes):**

1. **API Client**: Add chat endpoint function
2. **Interfaces**: Update `ranked_genes` → `ranked_entities`, `gene_name` → `entity_name`
3. **Search Form**: Add 'chat' option to existing search types
4. **Analysis Display**: Update field names in existing components
5. **Optional**: Simple chat component integration

### **What's NOT Needed (Over-Engineered):**

- ❌ Complex state management (Redux, Context)
- ❌ Separate chat page/view
- ❌ Extensive CSS overhaul
- ❌ Complex navigation changes
- ❌ Virtual scrolling or performance optimizations
- ❌ Extensive error handling

## 🚀 Minimal Migration Checklist

- [ ] Add chat API function to existing client
- [ ] Update analysis response interfaces (rename fields)
- [ ] Add 'chat' option to existing search type selector
- [ ] Update analysis display component field names
- [ ] Test chat functionality
- [ ] Test analysis display with new field names

## 💡 Implementation Strategy

**Option 1: Minimal Integration**
- Add chat as a search type option
- Integrate simple chat into existing search interface
- Update only the necessary field names

**Option 2: Separate Chat (Optional)**
- Create simple chat component
- Add chat link to existing navigation
- Keep chat separate from search flow

**Recommendation**: Start with Option 1 (minimal integration) and add Option 2 later if needed.

## 📝 Key Changes Summary

| Component | Change Required | Effort |
|-----------|----------------|---------|
| API Client | Add `sendChatMessage()` function | 5 minutes |
| Search Form | Add 'chat' to search types | 2 minutes |
| Analysis Display | Rename `gene_name` → `entity_name` | 5 minutes |
| Interfaces | Update response types | 3 minutes |
| **Total** | **4 small changes** | **~15 minutes** |

The frontend updates are much simpler than initially proposed. Focus on these minimal changes to get the new functionality working quickly. 