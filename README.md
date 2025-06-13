# Da Nang Tour Guide 🏖️

A smart local guide chatbot for Da Nang, Vietnam, powered by hybrid search and AI. Get personalized recommendations for food, attractions, and accommodation with local insights.

## Features

- **Category-based Search**: Browse by Eat 🍜, See 🏞️, or Stay 🏨
- **Hybrid Search**: Combines keyword (BM25) and semantic (vector) search for accurate results
- **AI-Powered Responses**: Uses Google's Gemma model for natural language responses
- **Local Expertise**: Curated database of authentic Da Nang places with prices, hours, and insider tips

## Quick Start

### Prerequisites
- Python 3.12+
- Docker & Docker Compose
- Google AI API key

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/koshiroquoc/DaNangtourguide.git
   cd DaNangtourguide
   ```

2. **Set up environment**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure API key**
   Create `.env` file:
   ```
   GOOGLE_API_KEY=your_google_ai_api_key_here
   ```

4. **Start Elasticsearch**
   ```bash
   docker-compose up -d
   ```

5. **Run the application**
   ```bash
   cd localguide_assistant
   streamlit run app_final_version.py
   ```

Visit `http://localhost:8501` to start exploring Da Nang!

## Architecture

The system uses a layered architecture with clear separation of concerns:

- **UI Layer**: [1](#0-0)  - Streamlit web interface with category navigation
- **RAG Pipeline**: [2](#0-1)  - Hybrid search + LLM generation
- **Search Engine**: [3](#0-2)  - Elasticsearch with BM25 and vector search
- **Infrastructure**: Docker containerized Elasticsearch service

## Usage

1. **Select Category**: Choose from Eat, See, or Stay options
2. **Ask Questions**: Type natural language queries like:
   - "Where can I find good pho for breakfast?"
   - "What are the best beaches near the city center?"
   - "Recommend budget hotels under $30/night"
3. **Get Local Insights**: Receive detailed responses with prices, locations, hours, and local tips

## Technical Details

### Hybrid Search Implementation
- **BM25 Search**: [4](#0-3)  - Keyword-based search with field boosting
- **Vector Search**: Semantic search using SentenceTransformer embeddings
- **Result Fusion**: [5](#0-4)  - Reciprocal Rank Fusion (RRF) combines both approaches

### Data Processing
- **Query Preprocessing**: [6](#0-5)  - SpaCy NLP for noun chunk extraction
- **Category Filtering**: Type-based filtering for eat/see/stay categories
- **Response Generation**: [7](#0-6)  - Google Gemma model integration

## Development

### Project Structure
```
localguide_assistant/
├── app_final_version.py    # Main Streamlit application
├── Hybridsearch.py         # RAG pipeline implementation
├── Indexing.py            # Elasticsearch data indexing
└── Images/                # UI assets

Data/
└── data_danang_ok.csv     # Tourism database

NoteBook/
├── Hybridsearch_test.ipynb # Development notebook
└── evaluation.ipynb       # System evaluation
```

### Version History
- **v1** ( [8](#0-7) ): Basic Streamlit implementation
- **v2** ( [9](#0-8) ): Enhanced UI with custom styling
- **v3** ( [10](#0-9) ): Production version with category captions and responsive design

## Contributing

1. Fork the repository
2. Create a feature branch
3. Test your changes with the evaluation notebook
4. Submit a pull request

## License

This project is open source and available under the MIT License.

## Contact

- GitHub: [@koshiroquoc](https://github.com/koshiroquoc)
- Instagram: @Koshiroquoc

---

*Built with ❤️ for travelers exploring the beautiful city of Da Nang*
```
