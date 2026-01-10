#!/usr/bin/env python3
"""
Extract RunningWritings content from provided web content

Since the site blocks automated crawling, this extracts content
from web search results or manually provided content.
"""
import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_db_sync
from models import CoachingKnowledgeEntry


def extract_from_web_content():
    """Extract content from web search results."""
    
    # Articles from the web search results
    articles = [
        {
            "title": "The principles of modern marathon training",
            "url": "https://runningwritings.com/principles-of-modern-marathon-training/",
            "content": """
The principles of modern marathon training

If you are trying to run a good marathon, not just get to the finish line, how should you train? That was the question I set out to answer when I started coaching marathoners over 12 years ago.

The complete answer to that question deserves (and gets) a full book-length treatment, but in this article, I want to distill the modern approach to marathon training down to its most essential core principles.

What is our goal in marathon training?

The basic proposition of the marathon is simple: our goal is to run 26.2 miles as fast as possible. Doing so requires a very specific set of physiological, biomechanical, and psychological capabilities. We need to build up these capabilities step by step, respecting the underlying principles of proper training.

Proper training for the marathon has many facets and details, but the broad strokes can be understood through five simple principles:
""",
            "categories": ["Marathon"],
            "tags": ["marathon", "physiology"]
        },
        {
            "title": "A guide to post-race workouts for runners",
            "url": "https://runningwritings.com/guide-to-post-race-workouts/",
            "content": """
A guide to post-race workouts for runners

Track season is nearly upon us and that's got me thinking about a very track-centric question: when, if ever, should you do a workout after doing a race?

This strategy—a post-race workout—When used correctly, post-race workouts can help maintain an adequate training load and balance out the distribution of speeds within your training schedule, even when you're racing frequently or have scheduling obligations to compete early in the season, when you'd like to be getting in more general and supportive training.

So, let's take a look at what post race workouts are, who should use them, and when.
""",
            "categories": ["Training"],
            "tags": ["3k", "5k", "800m", "college", "high school", "mile"]
        },
        {
            "title": "Understanding tissue loading, tissue damage, and running injuries",
            "url": "https://runningwritings.com/tissue-loading-tissue-damage-running-injuries/",
            "content": """
Understanding tissue loading, tissue damage, and running injuries

In my article on biomechanical training load, I covered the basics behind how biomechanical loading is related to the development of running injuries.

The basic idea is pretty straightforward: every time you take a step, your tendons, bones, and joints experience a loading cycle: a build-up and release of mechanical force.

Each loading cycle does a tiny amount of damage, depending on the magnitude of the force and the structural integrity of the tissue. If this damage accumulates faster than your body can repair it, the result is an overuse injury.

In this article, we're going to take a deeper dive into exactly how this process of tissue damage works. Our goal is to build up an understanding of cumulative damage: a way of quantifying "how much damage" you've done to a specific piece of tissue.

We'll use the recurring example of damage done to the Achilles tendon, since it's a common injury and a relatively straightforward tissue in terms of understanding both its biomechanical loading and its tissue properties.

So, what is the actual mechanical process behind tissue damage in running? Let's dive in and find out.
""",
            "categories": ["Biomechanics", "Science"],
            "tags": []
        },
        {
            "title": "A high-level picture of psychological training load for runners",
            "url": "https://runningwritings.com/psychological-training-load-runners/",
            "content": """
A high-level picture of psychological training load for runners

This is the third article in my series on unpacking what runners mean when they talk about "training load." The first two articles covered physiological training load and biomechanical training load. Today, we will turn our attention to the fascinating, subjective, and little-studied topic of psychological training load.

What is psychological training load? Put briefly, psychological training load describes the mental and emotional effects of training—both in terms of your short-term cognitive state and your longer-term psychological orientation.

Proper psychological training load drives motivation: both in the short-term sense of ability to summon a maximal effort and endure fatigue in a workout or race, and the long-term ability to believe in yourself, believe in your training, and believe in what you can achieve.

This discussion is going to be much more philosophical than the previous two articles. We'll cover the quantitative side first, but I'm much more interested in broader and more expansive views on athlete psychology than you typically see discussed in the scientific literature.

Tellingly, when you hear great coaches discuss their training approach, they often put quite a lot of emphasis on the psychological side of things. My own experience is similar: much of the work I do as a coach is managing athlete psychology and mindset—figuring out how to do the workouts, as well as what workouts to do.
""",
            "categories": ["coaching", "Training"],
            "tags": ["psychology"]
        },
        {
            "title": "A high-level picture of biomechanical training load for runners",
            "url": "https://runningwritings.com/biomechanical-training-load-runners/",
            "content": """
A high-level picture of biomechanical training load for runners

What do we mean when we say "training load"? This is the second article in a three-part series aimed at answering that question.

My core argument in this series is that there are three distinct types of training load you should consider—physiological training load, biomechanical training load, and psychological training load.

Today, we turn our attention to the second of these types of load. What exactly is biomechanical training load? In short:

Biomechanical training load describes the mechanical force—and ultimately, the mechanical damage—experienced by the load-bearing tissues of your body: bones, tendons, muscles, ligaments, and joint surfaces.

When talking about biomechanical training load, what we mean is "how much physical damage are you doing to your body."

Proper biomechanical training load drives health and structural integrity: the ability to avoid injury and increase your body's ability to sustain higher levels of training in the future.
""",
            "categories": ["Biomechanics", "Science", "Training"],
            "tags": ["achilles", "injury", "training"]
        }
    ]
    
    return articles


def store_articles():
    """Store articles in knowledge base."""
    db = get_db_sync()
    try:
        articles = extract_from_web_content()
        
        print(f"📚 Extracting {len(articles)} articles from RunningWritings.com")
        
        stored_count = 0
        for article in articles:
            print(f"\n[{stored_count + 1}/{len(articles)}] Storing: {article['title']}")
            
            entry = CoachingKnowledgeEntry(
                source="RunningWritings.com - John Davis",
                methodology="Davis",
                source_type="web_article",
                text_chunk=article["content"][:2000],  # Preview
                extracted_principles=json.dumps({
                    "title": article["title"],
                    "url": article["url"],
                    "categories": article["categories"],
                    "tags": article["tags"],
                    "full_text": article["content"]
                }),
                principle_type="article",
                metadata_json=json.dumps({
                    "url": article["url"],
                    "title": article["title"],
                    "categories": article["categories"],
                    "tags": article["tags"]
                })
            )
            db.add(entry)
            stored_count += 1
            
            print(f"  ✅ Stored ({len(article['content'])} chars)")
        
        db.commit()
        print(f"\n✅ Stored {stored_count} articles in knowledge base")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


def main():
    """Main function."""
    store_articles()
    print("✅ Done!")


if __name__ == "__main__":
    main()

