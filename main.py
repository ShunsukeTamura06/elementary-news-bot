#!/usr/bin/env python3
# main.py
import os
import logging
from datetime import datetime
import argparse
import schedule
import time
import json

from openai import OpenAI
from openai.types.beta.agent import Agent
from openai.types.beta.tool import Tool, Function, ToolType
from openai.types.beta.threads import Thread, ThreadMessage

from services.note_poster_service import NotePosterService
from models.article import Article

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load configuration
def load_config():
    """Load configuration from config.json file or environment variables"""
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        # If config file doesn't exist, use environment variables
        config = {
            "openai_api_key": os.environ.get("OPENAI_API_KEY"),
            "news_api_key": os.environ.get("NEWS_API_KEY"),
            "note_email": os.environ.get("NOTE_EMAIL"),
            "note_password": os.environ.get("NOTE_PASSWORD"),
            "post_time": os.environ.get("POST_TIME", "08:00"),
            "model": os.environ.get("OPENAI_MODEL", "gpt-4o"),
        }
    
    # Validate required configuration
    required_keys = ["openai_api_key", "news_api_key", "note_email", "note_password"]
    for key in required_keys:
        if not config.get(key):
            raise ValueError(f"Missing required configuration: {key}")
    
    return config

# Initialize OpenAI client
def initialize_openai_client(api_key):
    """Initialize the OpenAI client with the API key"""
    return OpenAI(api_key=api_key)

# Create news collection tool
def create_news_collection_tool(news_api_key):
    """Create a tool for collecting news using News API"""
    return Tool(
        type=ToolType.function,
        function=Function(
            name="fetch_trending_news",
            description="Fetches trending news from Japan using NewsAPI",
            parameters={
                "type": "object",
                "properties": {
                    "num_articles": {
                        "type": "integer",
                        "description": "Number of articles to fetch (max 10)"
                    },
                    "category": {
                        "type": "string",
                        "enum": ["general", "business", "entertainment", "health", "science", "sports", "technology"],
                        "description": "Category of news to fetch"
                    },
                    "age_appropriate": {
                        "type": "boolean",
                        "description": "Whether to filter for content appropriate for elementary school students",
                        "default": True
                    }
                },
                "required": ["num_articles"]
            }
        )
    )

# Function to fetch trending news (will be called by the agent)
def fetch_trending_news(num_articles, category="general", age_appropriate=True):
    """Fetch trending news from Japan using NewsAPI"""
    import requests
    
    config = load_config()
    news_api_key = config["news_api_key"]
    client = initialize_openai_client(config["openai_api_key"])
    
    url = f"https://newsapi.org/v2/top-headlines"
    params = {
        "country": "jp",
        "apiKey": news_api_key,
        "category": category,
        "pageSize": min(num_articles * 2, 20),  # Fetch more for filtering
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        raw_articles = []
        for article in data.get("articles", []):
            raw_articles.append({
                "title": article.get("title", ""),
                "description": article.get("description", ""),
                "content": article.get("content", ""),
                "url": article.get("url", ""),
                "publishedAt": article.get("publishedAt", ""),
                "source": article.get("source", {}).get("name", "")
            })
        
        # If age-appropriate filtering is enabled, use OpenAI to filter content
        if age_appropriate and raw_articles:
            filtered_articles = []
            
            for article in raw_articles:
                # Create a simple prompt for content filtering
                prompt = f"""
                評価してください: この以下の記事は小学生低学年（6〜8歳）に適切ですか？
                記事のタイトル: {article['title']}
                記事の概要: {article['description']}
                記事の内容: {article['content']}
                
                以下の基準で評価してください:
                1. 暴力的な内容が含まれていないか
                2. 政治的に議論を呼ぶ内容が含まれていないか
                3. 性的な内容が含まれていないか
                4. 子供が理解できる内容か
                5. 教育的価値があるか
                
                'YES'または'NO'で答えてください。その後に短い理由を書いてください。
                """
                
                response = client.chat.completions.create(
                    model=config["model"],
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                )
                
                result = response.choices[0].message.content
                
                # If the model thinks it's appropriate, add to filtered list
                if result.startswith("YES"):
                    filtered_articles.append(article)
                    if len(filtered_articles) >= num_articles:
                        break
            
            return filtered_articles[:num_articles]
        
        return raw_articles[:num_articles]
        
    except Exception as e:
        logger.error(f"Error fetching news: {str(e)}")
        return []

# Create an agent for news collection
def create_news_collection_agent(client):
    """Create an agent for collecting trending news"""
    news_tool = create_news_collection_tool(load_config()["news_api_key"])
    
    agent = Agent.create(
        client=client,
        name="NewsCollector",
        description="Agent that collects trending news from Japan",
        instructions="""
        You are a news collection agent specialized in gathering trending Japanese news.
        Your task is to:
        1. Collect the latest trending news from Japan
        2. Focus on news that would be interesting and appropriate for elementary school students
        3. Select a diverse range of topics (science, technology, sports, culture, etc.)
        4. Avoid sensitive, violent, or controversial topics
        5. Prioritize educational and positive news when possible
        
        Return the collected news in a structured format.
        """,
        tools=[news_tool],
        model=load_config()["model"]
    )
    
    return agent

# Create an agent for content simplification
def create_content_simplification_agent(client):
    """Create an agent for simplifying news content for elementary school students"""
    agent = Agent.create(
        client=client,
        name="ContentSimplifier",
        description="Agent that simplifies news content for elementary school students",
        instructions="""
        You are a content simplification agent specialized in making news understandable for lower elementary school students (ages 6-8).
        Your task is to:
        1. Take trending news articles and transform them into child-friendly content
        2. Use simple language appropriate for 1st-3rd grade students
        3. Explain complex concepts in easy-to-understand terms
        4. Structure content with clear headings and short paragraphs
        5. Include educational elements that help children learn about the world
        6. Make the content engaging and interesting for young readers
        7. Always maintain accuracy while simplifying
        8. Format the content in Markdown with proper formatting
        
        The final output should be a complete article in Markdown format with:
        - A catchy title (# Title)
        - Introduction explaining what the news is about
        - 3-4 sections with appropriate subheadings (## Subheading)
        - Simple explanations of any difficult concepts
        - A brief conclusion
        
        Remember to use hiragana for difficult kanji when necessary for the target age group.
        """,
        tools=[],
        model=load_config()["model"]
    )
    
    return agent

# Main function to process and post news
def process_and_post_news():
    """Main function to collect, process, and post news"""
    logger.info("Starting news processing and posting")
    
    try:
        # Load configuration
        config = load_config()
        
        # Initialize OpenAI client
        client = initialize_openai_client(config["openai_api_key"])
        
        # Create agents
        news_agent = create_news_collection_agent(client)
        content_agent = create_content_simplification_agent(client)
        
        # Create a thread for multi-agent collaboration
        thread = Thread.create(client=client)
        logger.info(f"Created new thread: {thread.id}")
        
        # Step 1: Collect trending news
        logger.info("Collecting trending news")
        
        # Create a message to start the news collection
        message = ThreadMessage.create(
            client=client,
            thread_id=thread.id,
            role="user",
            content=f"今日（{datetime.now().strftime('%Y年%m月%d日')}）の日本の小学生向けニュースを5つ探してください。興味深く、教育的で、小学生低学年に適切なものを選んでください。"
        )
        
        # Start a run with the news collection agent
        news_run = news_agent.runs.create(
            thread_id=thread.id,
            instructions="日本の最新ニュースから子供向けに適切なものを選んでください。暴力的、性的、または政治的に議論を呼ぶ内容は避けてください。"
        )
        
        # Handle the news collection agent's tool calls
        while news_run.status == "in_progress" or news_run.status == "requires_action":
            news_run = news_agent.runs.retrieve(news_run.id)
            
            if news_run.status == "requires_action" and news_run.required_action and news_run.required_action.type == "submit_tool_outputs":
                tool_outputs = []
                for tool_call in news_run.required_action.submit_tool_outputs.tool_calls:
                    if tool_call.function.name == "fetch_trending_news":
                        args = json.loads(tool_call.function.arguments)
                        num_articles = args.get("num_articles", 5)
                        category = args.get("category", "general")
                        age_appropriate = args.get("age_appropriate", True)
                        result = fetch_trending_news(num_articles, category, age_appropriate)
                        tool_outputs.append({
                            "tool_call_id": tool_call.id,
                            "output": json.dumps(result)
                        })
                
                news_run = news_agent.runs.submit_tool_outputs(
                    run_id=news_run.id,
                    tool_outputs=tool_outputs
                )
            
            time.sleep(1)
        
        # Check if news collection was successful
        if news_run.status != "completed":
            logger.error(f"News collection failed with status: {news_run.status}")
            if getattr(news_run, 'last_error', None):
                logger.error(f"Error details: {news_run.last_error}")
            return False
        
        # Get the messages from the thread to extract the collected news
        messages = client.beta.threads.messages.list(thread_id=thread.id)
        collected_news = ""
        for msg in messages.data:
            if msg.role == "assistant" and msg.run_id == news_run.id:
                collected_news = msg.content[0].text.value
                break
        
        logger.info(f"News collection completed: {len(collected_news)} characters")
        
        # Step 2: Simplify content for elementary school students
        logger.info("Simplifying content for elementary school students")
        
        # Add a message to instruct the content simplification
        message = ThreadMessage.create(
            client=client,
            thread_id=thread.id,
            role="user",
            content=f"""
            上記のニュースから1つを選んで、小学校低学年（1〜3年生）向けの記事を作成してください。
            
            次の点に注意してください：
            1. 簡単な言葉と短い文を使う
            2. 難しい漢字にはふりがなをつける
            3. 明確な見出しと短い段落を使う
            4. 教育的な要素を含める
            5. 子どもが興味を持つように書く
            
            記事はマークダウン形式で作成し、以下の構成にしてください：
            - キャッチーなタイトル（# タイトル）
            - ニュースの概要を説明する導入部
            - 3〜4つのセクション（## 見出し）
            - 難しい概念の簡単な説明
            - 簡単なまとめ
            """
        )
        
        # Start a run with the content simplification agent
        content_run = content_agent.runs.create(
            thread_id=thread.id,
            instructions="小学校低学年（6〜8歳）向けにニュース記事を作成してください。簡単な言葉、短い文、明確な構成で書いてください。"
        )
        
        # Wait for content simplification to complete
        while content_run.status == "in_progress" or content_run.status == "requires_action":
            content_run = content_agent.runs.retrieve(content_run.id)
            time.sleep(1)
        
        # Check if content simplification was successful
        if content_run.status != "completed":
            logger.error(f"Content simplification failed with status: {content_run.status}")
            if getattr(content_run, 'last_error', None):
                logger.error(f"Error details: {content_run.last_error}")
            return False
        
        # Get the messages from the thread to extract the simplified content
        messages = client.beta.threads.messages.list(thread_id=thread.id)
        simplified_content = ""
        for msg in messages.data:
            if msg.role == "assistant" and msg.run_id == content_run.id:
                simplified_content = msg.content[0].text.value
                break
        
        logger.info(f"Content simplification completed: {len(simplified_content)} characters")
        
        # Add a step to validate the simplified content
        logger.info("Validating simplified content")
        validate_message = ThreadMessage.create(
            client=client,
            thread_id=thread.id,
            role="user",
            content="この記事の内容は小学校低学年向けに適切ですか？文章の難易度、使われている言葉、構成などが対象年齢に合っているか確認してください。改善点があれば具体的に指摘してください。"
        )
        
        # Start a run with the content agent to validate
        validate_run = content_agent.runs.create(
            thread_id=thread.id,
            instructions="記事の難易度、語彙、構成が小学校低学年（6〜8歳）向けに適切か評価し、必要に応じて改善を提案してください。"
        )
        
        # Wait for validation to complete
        while validate_run.status == "in_progress":
            validate_run = content_agent.runs.retrieve(validate_run.id)
            time.sleep(1)
            
        # Get validation feedback
        messages = client.beta.threads.messages.list(thread_id=thread.id)
        validation_feedback = ""
        for msg in messages.data:
            if msg.role == "assistant" and msg.run_id == validate_run.id:
                validation_feedback = msg.content[0].text.value
                break
                
        logger.info(f"Content validation completed")
        
        # If validation suggests improvements, request a revised version
        if "改善" in validation_feedback or "修正" in validation_feedback:
            logger.info("Requesting content improvements based on validation")
            improve_message = ThreadMessage.create(
                client=client,
                thread_id=thread.id,
                role="user",
                content="指摘された改善点に基づいて、記事を修正してください。小学校低学年の子どもが理解できるように、さらに平易な言葉と表現を使ってください。"
            )
            
            # Start a run with the content agent to improve
            improve_run = content_agent.runs.create(
                thread_id=thread.id,
                instructions="フィードバックに基づいて記事を改善し、小学校低学年向けにさらに簡潔で分かりやすくしてください。"
            )
            
            # Wait for improvement to complete
            while improve_run.status == "in_progress":
                improve_run = content_agent.runs.retrieve(improve_run.id)
                time.sleep(1)
                
            # Get improved content
            messages = client.beta.threads.messages.list(thread_id=thread.id)
            for msg in messages.data:
                if msg.role == "assistant" and msg.run_id == improve_run.id:
                    simplified_content = msg.content[0].text.value
                    break
                    
            logger.info("Content improvements completed")
        
        # Step 3: Post to note.com
        logger.info("Posting content to note.com")
        note_poster = NotePosterService(config["note_email"], config["note_password"])
        
        # Create article object
        article = Article(
            title="",  # Title will be extracted from Markdown content
            content=simplified_content,
            status="draft",
            created_at=datetime.now(),
            improved_content=None
        )
        
        # Post article
        post_success = note_poster.post_article(article)
        
        if post_success:
            logger.info("Article posted successfully!")
            
            # Archive the thread for reference
            thread_archive = {
                "thread_id": thread.id,
                "date": datetime.now().isoformat(),
                "article_content": simplified_content
            }
            
            # Save thread archive
            os.makedirs("archives", exist_ok=True)
            with open(f"archives/thread_{datetime.now().strftime('%Y%m%d')}.json", "w") as f:
                json.dump(thread_archive, f, ensure_ascii=False, indent=2)
            
            return True
        else:
            logger.error("Failed to post article")
            return False
            
    except Exception as e:
        logger.error(f"Error in process_and_post_news: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

# Schedule function
def setup_scheduler():
    """Set up a scheduler to run the process daily"""
    config = load_config()
    post_time = config.get("post_time", "08:00")
    
    logger.info(f"Setting up scheduler to run daily at {post_time}")
    schedule.every().day.at(post_time).do(process_and_post_news)

# Run scheduler
def run_scheduler():
    """Run the scheduler"""
    logger.info("Starting scheduler")
    while True:
        schedule.run_pending()
        time.sleep(60)

# Run immediately or with scheduler
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Elementary News Bot")
    parser.add_argument("--now", action="store_true", help="Run immediately instead of scheduling")
    args = parser.parse_args()
    
    if args.now:
        logger.info("Running immediately")
        process_and_post_news()
    else:
        setup_scheduler()
        run_scheduler()