# Frontend Build Guide - GeneSearch v2.0

## 🎯 Overview

This guide provides detailed guidelines for building a flexible, scalable frontend for GeneSearch v2.0 from scratch. The focus is on creating a system that can handle any biological question, not just gene-specific queries.

## 🏗️ Architecture Guidelines

### 1. **Component Structure**
```
src/
├── components/
│   ├── common/           # Reusable UI components
│   ├── search/           # Search-related components
│   ├── analysis/         # Analysis display components
│   ├── chat/            # Chat interface components
│   └── layout/          # Layout and navigation
├── services/            # API integration
├── types/              # TypeScript interfaces
├── hooks/              # Custom React hooks
├── utils/              # Utility functions
└── config/             # Configuration files
```

### 2. **State Management Strategy**
- **Local State**: Use React useState for component-specific state
- **Shared State**: Use React Context for app-wide state (search results, chat history)
- **Persistence**: Use localStorage for conversation history and user preferences
- **Avoid**: Redux for this scale - keep it simple

### 3. **API Integration Pattern**
- **Service Layer**: Centralized API calls in `/services`
- **Error Handling**: Consistent error handling across all API calls
- **Loading States**: Standardized loading state management
- **Retry Logic**: Implement retry for failed requests

## 📋 Core Components Guidelines

### 1. **Search Interface**

#### **Flexible Search Form**
- **Dynamic Placeholders**: Change based on search type
- **Adaptive Options**: Show/hide options based on search type
- **Query Validation**: Validate input before sending
- **Search History**: Remember recent searches

#### **Single Search Interface**
```typescript
// Single comprehensive search that handles any biological question
const SEARCH_CONFIG = {
  placeholder: "Ask any biological question (e.g., 'What genes are involved in salt tolerance?', 'How do plants respond to drought?')",
  description: "Comprehensive biological analysis with live streaming results"
};
```

#### **Search Features**
- **Natural Language Input**: Accept any biological question
- **Live Streaming**: Real-time analysis results
- **Follow-up Questions**: Interactive chat on analysis results
- **Context Preservation**: Maintain conversation context

### 2. **Live Analysis Display**

#### **Streaming Results**
- **Real-time Updates**: Live streaming of analysis as it's generated
- **Progressive Display**: Show results as they become available
- **Loading Indicators**: Visual feedback during streaming
- **Error Handling**: Graceful handling of streaming interruptions

#### **Analysis Sections**
- **Live Executive Summary**: Updates as analysis progresses
- **Dynamic Entity Discovery**: Entities appear as they're found
- **Evidence Accumulation**: Evidence builds up in real-time
- **Live Recommendations**: Recommendations evolve with analysis
- **Source Tracking**: Sources are added as they're discovered

#### **Agent Activity Tracking**
- **Gene Search Agent**: Shows which databases were searched and what was found
- **Web Research Agent**: Displays literature search progress and paper discoveries
- **Analysis Agent**: Shows real-time analysis generation
- **Tool Execution**: Displays which tools were used and their results

#### **Responsive Design**
- **Mobile-First**: Ensure mobile compatibility
- **Tablet Optimization**: Optimize for tablet viewing
- **Desktop Enhancement**: Enhanced features for desktop

### 3. **Follow-up Chat Interface**

#### **Analysis-Based Chat**
- **Context-Aware**: Chat has full context of the analysis
- **Follow-up Questions**: Ask questions about the analysis results
- **Entity References**: Reference specific entities from analysis
- **Conversation Continuity**: Maintain context across follow-ups

#### **Chat Features**
- **Analysis Context**: Chat knows about the current analysis
- **Entity Linking**: Click on entities to ask follow-up questions
- **Evidence Queries**: Ask for more details about specific evidence
- **Recommendation Expansion**: Get more details on recommendations

#### **Integration with Analysis**
- **Seamless Flow**: Analysis → Chat → Follow-up → New Analysis
- **Context Preservation**: Analysis context carried to chat
- **Result Sharing**: Share analysis results in chat
- **Quick Actions**: Generate new analysis from chat

## 🎨 UI/UX Guidelines

### 1. **Design System**

#### **Color Palette**
```css
/* Primary Colors */
--primary-blue: #007bff;
--primary-green: #28a745;
--primary-orange: #fd7e14;

/* Semantic Colors */
--success: #28a745;
--warning: #ffc107;
--danger: #dc3545;
--info: #17a2b8;

/* Neutral Colors */
--light-gray: #f8f9fa;
--medium-gray: #6c757d;
--dark-gray: #343a40;
```

#### **Typography**
- **Font Family**: System fonts for performance
- **Font Sizes**: Responsive scale (12px - 32px)
- **Line Heights**: 1.4 - 1.6 for readability
- **Font Weights**: 400 (normal), 500 (medium), 600 (semibold), 700 (bold)

#### **Spacing System**
```css
/* 8px base spacing unit */
--spacing-xs: 4px;
--spacing-sm: 8px;
--spacing-md: 16px;
--spacing-lg: 24px;
--spacing-xl: 32px;
--spacing-xxl: 48px;
```

### 2. **Component Guidelines**

#### **Buttons**
- **Primary**: Main actions (Search, Send)
- **Secondary**: Supporting actions (Clear, Export)
- **Tertiary**: Minor actions (Copy, Bookmark)
- **States**: Default, hover, active, disabled, loading

#### **Forms**
- **Input Fields**: Clear labels, validation messages
- **Select Dropdowns**: Searchable, multi-select support
- **Checkboxes/Radios**: Clear grouping and labels
- **Form Validation**: Real-time validation with clear messages

#### **Cards**
- **Entity Cards**: Flexible content areas
- **Analysis Cards**: Structured information display
- **Chat Cards**: Message bubbles with metadata

### 3. **Responsive Design**

#### **Breakpoints**
```css
/* Mobile First */
--mobile: 320px;
--tablet: 768px;
--desktop: 1024px;
--large-desktop: 1440px;
```

#### **Layout Patterns**
- **Single Column**: Mobile (320px - 767px)
- **Two Column**: Tablet (768px - 1023px)
- **Multi Column**: Desktop (1024px+)

## 🔧 Technical Guidelines

### 1. **TypeScript Configuration**

#### **Strict TypeScript**
```json
{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true,
    "strictNullChecks": true,
    "strictFunctionTypes": true
  }
}
```

#### **Interface Design**
```typescript
// Gene Search Agent Results
interface GeneSearchResult {
  user_trait: string;
  explanation?: string;
  genes: GeneHit[];
  gwas_hits: GWASHit[];
  go_annotations: GOAnnot[];
  pathways: Pathway[];
  pubmed_summaries: PubMedSummary[];
  metadata: ToolExecutionMetadata[];
  execution_time: number;
}

interface GeneHit {
  gene_id: string;
  symbol?: string;
  description?: string;
  species?: string;
  chromosome?: string;
  start?: number;
  end?: number;
  source: string; // 'ensembl' | 'gramene'
}

interface GWASHit {
  gene_name: string;
  pvalue: number;
  trait?: string;
  variant_id?: string;
  effect_allele?: string;
  sample_size?: number;
  pubmed_id?: string;
  study_accession?: string;
}

interface GOAnnot {
  go_id?: string;
  term?: string;
  aspect?: string; // P (BP), F (MF) or C (CC)
  evidence_code?: string;
  reference?: string;
  qualifier?: string;
}

interface Pathway {
  pathway_id: string;
  description?: string;
  database?: string; // KEGG, Reactome, etc.
}

interface PubMedSummary {
  pmid: string;
  title: string;
  abstract?: string;
  doi?: string;
  url?: string;
  journal?: string;
  pubdate?: string;
  authors?: string[];
}

interface ToolExecutionMetadata {
  tool: string;
  execution_time: number;
  success: boolean;
  error?: string;
  prompt_tokens?: number;
  completion_tokens?: number;
  rows_returned?: number;
  timestamp: string;
}

// Web Research Agent Results
interface WebResearchAgentModel {
  query: string;
  raw_result: string;
  research_paper: WebResearchResult;
  upnext_queries: string[];
  biological_analysis?: any;
}

interface WebResearchResult {
  search_result: SearchResult[];
}

interface SearchResult {
  title: string;
  url: string;
  abstract: string;
}

// Analysis Service Results
interface AnalysisResult {
  ranked_entities: RankedEntity[];
  analysis_summary: AnalysisSummary;
  sources_analyzed: SourcesAnalyzed;
  recommendations: string[];
  biological_insights: string[];
  key_findings: string[];
  executive_summary: string;
}

interface RankedEntity {
  entity_name: string;
  priority_rank: number;
  evidence_summary: string;
  biological_hypothesis: string;
  confidence: 'High' | 'Medium' | 'Low';
  statistical_associations: number;
  publications: number;
  pathways_processes: number;
  ensembl_link?: string;
  ncbi_link?: string;
  uniprot_link?: string;
  genecards_link?: string;
}

interface AnalysisSummary {
  total_entities: number;
  total_associations: number;
  total_publications: number;
  total_pathways: number;
  key_insights: string[];
}

interface SourcesAnalyzed {
  gene_databases: number;
  web_sources: number;
  statistical_studies: number;
  functional_annotations: number;
}
```

### 2. **API Integration**

#### **Service Layer Pattern**
```typescript
// Generic API service
class APIService {
  private baseURL: string;
  private headers: Record<string, string>;

  constructor(config: APIConfig) {
    this.baseURL = config.baseURL;
    this.headers = config.headers;
  }

  async request<T>(endpoint: string, options?: RequestOptions): Promise<T> {
    // Standardized request handling
  }
}

// Research service with streaming
class ResearchService extends APIService {
  async streamResearch(query: string, onUpdate: (chunk: any) => void): Promise<void> {
    // Streaming research implementation
  }
}

// Individual agent services
class GeneSearchService extends APIService {
  async search(query: string): Promise<GeneSearchResult> {
    // Gene search implementation
  }
}

class WebResearchService extends APIService {
  async search(query: string): Promise<WebResearchAgentModel> {
    // Web research implementation
  }
}

class AnalysisService extends APIService {
  async analyze(geneResults: GeneSearchResult, webResults: WebResearchAgentModel): Promise<AnalysisResult> {
    // Analysis implementation
  }
}

// Chat service for follow-up questions
class ChatService extends APIService {
  async sendFollowUp(question: string, analysisContext: AnalysisContext): Promise<ChatResponse> {
    // Follow-up chat implementation
  }
}
```

#### **Error Handling**
```typescript
// Standardized error handling
interface APIError {
  code: string;
  message: string;
  details?: any;
}

class APIErrorHandler {
  static handle(error: any): APIError {
    // Standardized error processing
  }
}
```

### 3. **State Management**

#### **Context Pattern**
```typescript
// App-wide state
interface AppState {
  searchResults: SearchResult | null;
  chatHistory: ChatMessage[];
  userPreferences: UserPreferences;
  loadingStates: LoadingStates;
}

// Context providers
const AppContext = createContext<AppState | null>(null);
const AppDispatchContext = createContext<AppDispatch | null>(null);
```

#### **Custom Hooks**
```typescript
// Reusable hooks
const useResearch = () => {
  // Research streaming logic with agent tracking
};

const useFollowUpChat = () => {
  // Follow-up chat logic with analysis context
};

const useStreamingDisplay = () => {
  // Live streaming display logic
};

const useAgentTracking = () => {
  // Track agent activities and tool executions
};
```

## 📱 Mobile Guidelines

### 1. **Touch Interactions**
- **Touch Targets**: Minimum 44px for touch targets
- **Gesture Support**: Swipe, pinch, long press
- **Keyboard Handling**: Proper keyboard behavior

### 2. **Performance**
- **Lazy Loading**: Load components on demand
- **Image Optimization**: Responsive images, WebP format
- **Bundle Splitting**: Code splitting for faster loading

### 3. **Accessibility**
- **ARIA Labels**: Proper accessibility labels
- **Keyboard Navigation**: Full keyboard support
- **Screen Reader**: Screen reader compatibility
- **Color Contrast**: WCAG AA compliance

## 🚀 Development Guidelines

### 1. **Code Organization**
- **Feature-Based**: Organize by features, not types
- **Shared Components**: Extract reusable components
- **Utility Functions**: Centralize utility functions
- **Constants**: Centralize configuration constants

### 2. **Testing Strategy**
- **Unit Tests**: Test individual components
- **Integration Tests**: Test component interactions
- **E2E Tests**: Test complete user flows
- **Accessibility Tests**: Test accessibility compliance

### 3. **Performance Optimization**
- **React.memo**: Memoize expensive components
- **useMemo/useCallback**: Optimize re-renders
- **Virtual Scrolling**: For long lists
- **Code Splitting**: Lazy load routes

## 📊 Data Flow Guidelines

### 1. **Research Flow**
```
User Question → Validation → Gene Search Agent → Web Research Agent → Analysis Agent → Live Stream → Progressive Display → Follow-up Chat Ready
```

### 2. **Agent Activity Flow**
```
Gene Search: Database Queries → Tool Execution → Results Collection
Web Research: Literature Search → Paper Analysis → Structured Data
Analysis: Data Synthesis → AI Analysis → Streaming Output
```

### 3. **Streaming Flow**
```
Research Request → Agent Initialization → Tool Execution Updates → Results Streaming → Analysis Generation → Chat Enabled
```

## 🔄 Configuration Guidelines

### 1. **Environment Configuration**
```typescript
// config/environment.ts
interface Environment {
  API_BASE_URL: string;
  GENE_SEARCH_ENDPOINT: string;
  WEB_RESEARCH_ENDPOINT: string;
  ANALYSIS_ENDPOINT: string;
  RESEARCH_ENDPOINT: string;
  STREAM_RESEARCH_ENDPOINT: string;
  CHAT_ENDPOINT: string;
  MAX_CHAT_HISTORY: number;
  SEARCH_TIMEOUT: number;
  STREAM_TIMEOUT: number;
}
```

### 2. **Feature Flags**
```typescript
// config/features.ts
interface FeatureFlags {
  enableChat: boolean;
  enableAdvancedSearch: boolean;
  enableExport: boolean;
  enableAnalytics: boolean;
}
```

### 3. **Localization**
```typescript
// config/localization.ts
interface Localization {
  language: string;
  translations: Record<string, Record<string, string>>;
  dateFormat: string;
  numberFormat: string;
}
```

## 📈 Scalability Guidelines

### 1. **Component Scalability**
- **Composition**: Use composition over inheritance
- **Props Interface**: Flexible prop interfaces
- **Default Values**: Sensible defaults for all props
- **Validation**: PropTypes or TypeScript validation

### 2. **Data Scalability**
- **Pagination**: Handle large datasets
- **Virtualization**: For very large lists
- **Caching**: Cache frequently accessed data
- **Optimistic Updates**: Update UI before API response

### 3. **Performance Monitoring**
- **Metrics**: Track key performance metrics
- **Error Tracking**: Monitor and report errors
- **User Analytics**: Track user behavior
- **Performance Budgets**: Set performance targets

## 🎯 Implementation Priority

### **Phase 1: Core Functionality**
1. Single search interface with natural language input
2. Live streaming research display with agent tracking
3. Basic follow-up chat functionality
4. API integration for all agents (gene search, web research, analysis)

### **Phase 2: Enhanced Features**
1. Advanced streaming with agent activity indicators
2. Tool execution tracking and display
3. Entity linking in analysis results
4. Context-aware follow-up questions
5. Export and sharing functionality

### **Phase 3: Polish & Optimization**
1. Performance optimization for streaming
2. Accessibility improvements
3. Mobile optimization
4. Advanced chat features (entity references, evidence queries)
5. Detailed agent telemetry and analytics

This guide provides a comprehensive framework for building a flexible, scalable frontend that can handle any biological question while maintaining clean, maintainable code. 