"""
Apex features demonstration for KnowledgeReduce.

This example demonstrates all the advanced capabilities of KnowledgeReduce Apex,
including AI integration, multi-modal data, and federated collaboration.
"""
import os
import time
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np
from knowledge_graph_pkg.core import KnowledgeGraph, ReliabilityRating
from knowledge_graph_pkg.enhanced import EnhancedKnowledgeGraph
from knowledge_graph_pkg.ai import AIKnowledgeGraph
from knowledge_graph_pkg.multimodal import MultiModalKnowledgeGraph
from knowledge_graph_pkg.federated import FederatedKnowledgeGraph
from knowledge_graph_pkg.visualization import plot_knowledge_graph

def main():
    print("KnowledgeReduce Apex Example")
    print("============================\n")
    
    # Create output directory
    os.makedirs("output", exist_ok=True)
    os.makedirs("media", exist_ok=True)
    
    # Create a base knowledge graph with enhanced capabilities
    print("\n1. Creating Enhanced Knowledge Graph")
    print("----------------------------------")
    kg = EnhancedKnowledgeGraph(cache_enabled=True, auto_save_interval=60)
    
    # Add some initial facts
    print("Adding initial facts...")
    
    astronomy_facts = [
        {
            'fact_id': 'fact_001',
            'fact_statement': 'The Earth orbits the Sun',
            'category': 'Astronomy',
            'tags': ['earth', 'sun', 'orbit', 'solar system'],
            'reliability_rating': ReliabilityRating.VERIFIED
        },
        {
            'fact_id': 'fact_002',
            'fact_statement': 'Jupiter is the largest planet in our solar system',
            'category': 'Astronomy',
            'tags': ['jupiter', 'planet', 'solar system', 'size'],
            'reliability_rating': ReliabilityRating.VERIFIED
        },
        {
            'fact_id': 'fact_003',
            'fact_statement': 'The Moon orbits the Earth',
            'category': 'Astronomy',
            'tags': ['moon', 'earth', 'orbit', 'satellite'],
            'reliability_rating': ReliabilityRating.VERIFIED
        }
    ]
    
    # Add common fields to all facts
    now = datetime.now()
    for fact in astronomy_facts:
        fact.update({
            'date_recorded': now,
            'last_updated': now,
            'source_id': 'astronomy_textbook',
            'source_title': 'Principles of Astronomy',
            'author_creator': 'Dr. Neil Stargazer',
            'publication_date': now,
            'url_reference': 'https://example.com/astronomy',
            'related_facts': [],
            'contextual_notes': f"Basic fact about {fact['tags'][0]}",
            'access_level': 'public',
            'usage_count': 0
        })
    
    # Batch add facts
    kg.batch_add_facts(astronomy_facts)
    print(f"Added {len(astronomy_facts)} initial facts")
    
    # Part 2: AI Integration
    print("\n2. AI Integration")
    print("---------------")
    
    # Create an AI-enhanced knowledge graph
    ai_kg = AIKnowledgeGraph(kg, model_name="gpt-4")
    
    # Extract knowledge from text
    print("Extracting knowledge from text...")
    text = """
    Mars has two small moons, Phobos and Deimos. Phobos orbits Mars every 7 hours and 39 minutes,
    while Deimos takes 30 hours and 18 minutes. Venus is the hottest planet in our solar system
    due to its thick atmosphere that traps heat. Mercury is the smallest planet in our solar system
    and the closest to the Sun.
    """
    
    extracted_fact_ids = ai_kg.extract_knowledge_from_text(
        text=text,
        source_id="ai_extraction",
        reliability=ReliabilityRating.LIKELY_TRUE
    )
    
    print(f"Extracted {len(extracted_fact_ids)} facts from text")
    
    # Answer a question
    print("\nAnswering a question using AI reasoning...")
    question = "Which planets have moons in our solar system?"
    answer = ai_kg.answer_question(question)
    
    print(f"Question: {answer['question']}")
    print(f"Answer: {answer['answer']}")
    print("Supporting facts:")
    for fact in answer['supporting_facts']:
        print(f"  - {fact}")
    
    # Generate hypotheses
    print("\nGenerating hypotheses about planetary formation...")
    hypotheses = ai_kg.generate_hypotheses("planetary formation", num_hypotheses=2)
    
    print("Generated hypotheses:")
    for i, hypothesis in enumerate(hypotheses):
        print(f"Hypothesis {i+1}: {hypothesis['hypothesis']}")
        print(f"Confidence: {hypothesis['confidence']:.2f}")
        print(f"Potential tests: {', '.join(hypothesis['potential_tests'])}")
        print()
    
    # Explain reasoning
    print("Explaining reasoning behind a fact...")
    explanation = ai_kg.explain_reasoning("fact_001")
    
    print(f"Fact: {explanation['fact_statement']}")
    print(f"Explanation: {explanation['explanation']}")
    print(f"Confidence: {explanation['confidence']:.2f}")
    
    # Part 3: Multi-modal Knowledge
    print("\n3. Multi-modal Knowledge")
    print("----------------------")
    
    # Create a multi-modal knowledge graph
    mm_kg = MultiModalKnowledgeGraph(kg, media_dir="media")
    
    # Create a simple image (in a real scenario, you would use actual image files)
    print("Creating sample image data...")
    sample_image = create_sample_image()
    
    # Add image fact
    print("Adding image fact...")
    image_fact = mm_kg.add_image_fact(
        fact_id="image_fact_001",
        image_data=sample_image,
        caption="Diagram of the solar system showing planetary orbits",
        category="Astronomy",
        tags=["solar system", "planets", "orbits", "diagram"],
        reliability_rating=ReliabilityRating.VERIFIED,
        source_id="astronomy_diagrams",
        source_title="Visual Astronomy Guide",
        author_creator="Astronomy Visualizations Inc."
    )
    
    print(f"Added image fact: {image_fact['fact_id']}")
    print(f"Media info: {image_fact['media_info']['type']}, {image_fact['media_info']['filename']}")
    
    # Create a simple audio file (in a real scenario, you would use actual audio files)
    print("Creating sample audio data...")
    sample_audio = create_sample_audio()
    
    # Add audio fact
    print("Adding audio fact...")
    audio_fact = mm_kg.add_audio_fact(
        fact_id="audio_fact_001",
        audio_data=sample_audio,
        description="Recording of radio emissions from Jupiter",
        category="Astronomy",
        tags=["jupiter", "radio", "emissions", "recording"],
        reliability_rating=ReliabilityRating.LIKELY_TRUE,
        source_id="space_sounds",
        source_title="Sounds of the Solar System",
        author_creator="Space Acoustics Research Team"
    )
    
    print(f"Added audio fact: {audio_fact['fact_id']}")
    
    # Search for media facts
    print("\nSearching for media facts...")
    image_facts = mm_kg.search_media_facts(media_type="image")
    audio_facts = mm_kg.search_media_facts(media_type="audio")
    
    print(f"Found {len(image_facts)} image facts and {len(audio_facts)} audio facts")
    
    # Export media index
    mm_kg.export_media_index(os.path.join("output", "media_index.json"))
    print("Exported media index to output/media_index.json")
    
    # Part 4: Federated Collaboration
    print("\n4. Federated Collaboration")
    print("------------------------")
    
    # Create a federated knowledge graph
    fed_kg = FederatedKnowledgeGraph(kg, node_id="node_001")
    
    # Register users
    print("Registering users...")
    admin_user = fed_kg.register_user(
        user_id="user_001",
        username="Admin User",
        role="admin"
    )
    
    contributor_user = fed_kg.register_user(
        user_id="user_002",
        username="Contributor User",
        role="contributor"
    )
    
    viewer_user = fed_kg.register_user(
        user_id="user_003",
        username="Viewer User",
        role="viewer"
    )
    
    print(f"Registered {len(fed_kg.users)} users")
    
    # Create user sessions
    admin_session = fed_kg.create_user_session("user_001")
    contributor_session = fed_kg.create_user_session("user_002")
    
    print(f"Created user sessions: {admin_session['session_id']}, {contributor_session['session_id']}")
    
    # Add collaborative facts
    print("\nAdding collaborative facts...")
    
    admin_fact = fed_kg.add_fact_collaborative(
        user_id="user_001",
        fact_id="collab_fact_001",
        fact_statement="Neptune has 14 known moons",
        category="Astronomy",
        tags=["neptune", "moons", "solar system"],
        reliability_rating=ReliabilityRating.VERIFIED,
        source_id="collaborative_astronomy"
    )
    
    contributor_fact = fed_kg.add_fact_collaborative(
        user_id="user_002",
        fact_id="collab_fact_002",
        fact_statement="Saturn's rings are made mostly of ice particles",
        category="Astronomy",
        tags=["saturn", "rings", "ice", "solar system"],
        reliability_rating=ReliabilityRating.VERIFIED,
        source_id="collaborative_astronomy"
    )
    
    print(f"Added collaborative facts: {admin_fact['fact_id']}, {contributor_fact['fact_id']}")
    
    # Update a fact collaboratively
    print("Updating fact collaboratively...")
    update_result = fed_kg.update_fact_collaborative(
        user_id="user_001",
        fact_id="collab_fact_001",
        fact_statement="Neptune has 14 known moons, with Triton being the largest",
        tags=["neptune", "moons", "triton", "solar system"]
    )
    
    print(f"Updated fact: {update_result['fact_id']} (version: {update_result['version']})")
    
    # Add a peer node
    peer = fed_kg.add_peer(
        peer_id="node_002",
        peer_url="https://example.com/kg/node_002",
        peer_name="Astronomy Research Team"
    )
    
    print(f"Added peer: {peer['peer_name']} ({peer['peer_id']})")
    
    # Get user contributions
    admin_contributions = fed_kg.get_user_contributions("user_001")
    contributor_contributions = fed_kg.get_user_contributions("user_002")
    
    print("\nUser contributions:")
    print(f"Admin: {admin_contributions['total_changes']} changes, {admin_contributions['unique_facts']} facts")
    print(f"Contributor: {contributor_contributions['total_changes']} changes, {contributor_contributions['unique_facts']} facts")
    
    # Export federation state
    fed_kg.export_federation_state(os.path.join("output", "federation_state.json"))
    print("Exported federation state to output/federation_state.json")
    
    # Visualize the knowledge graph
    print("\nVisualizing knowledge graph...")
    plot_knowledge_graph(kg, os.path.join("output", "apex_knowledge_graph.png"))
    print("Saved visualization to output/apex_knowledge_graph.png")
    
    print("\nKnowledgeReduce Apex example completed successfully!")

def create_sample_image():
    """Create a sample image for demonstration purposes."""
    # In a real scenario, you would use an actual image file
    # This creates a simple binary representation for demonstration
    return b'SAMPLE_IMAGE_DATA_PLACEHOLDER'

def create_sample_audio():
    """Create a sample audio file for demonstration purposes."""
    # In a real scenario, you would use an actual audio file
    # This creates a simple binary representation for demonstration
    return b'SAMPLE_AUDIO_DATA_PLACEHOLDER'

if __name__ == "__main__":
    main()
