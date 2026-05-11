nine-lords-war/
│
├── requirements.txt                 # Dependencies (above)
├── .env                             # API Keys (create this)
├── .gitignore                       # Git ignore file
├── README.md                        # Project documentation
│
├── run.py                           # 🚀 Main entry point
│
├── core/                            # Core game engine
│   ├── __init__.py
│   ├── orchestrator.py              # Game main loop
│   ├── emperor.py                   # Human intervention (皇上)
│   ├── vote_engine.py               # Vote counting & elimination
│   └── config.py                    # Configuration loader
│
├── agents/                          # Agent definitions
│   ├── __init__.py
│   ├── base_agent.py                # Base Agent class
│   ├── agent_factory.py             # Create 9 agents
│   └── prompts/                     # Personality prompts
│       ├── __init__.py
│       ├── radical.txt              # 大阿哥 - 激进型
│       ├── stable.txt               # 二阿哥 - 稳健型
│       ├── cunning.txt              # 三阿哥 - 精明型
│       ├── reformer.txt             # 四阿哥 - 改革型
│       ├── loyal.txt                # 五阿哥 - 忠厚型
│       ├── utilitarian.txt          # 六阿哥 - 功利型
│       ├── idealist.txt             # 七阿哥 - 理想型
│       ├── schemer.txt              # 八阿哥 - 权谋型
│       └── impulsive.txt            # 九阿哥 - 焦躁型
│
├── memory/                          # Memory systems
│   ├── __init__.py
│   ├── chroma_memory.py             # Agent long-term memory (ChromaDB)
│   ├── shared_memory.py             # Public shared memory
│   └── game_archive.py              # Full game archive (ChromaDB)
│
├── storage/                         # Persistence
│   ├── __init__.py
│   ├── sqlite_storage.py            # SQLite for structured data
│   └── models.py                    # SQLite table definitions
│
├── rounds/                          # Round phase logic
│   ├── __init__.py
│   ├── submit.py                    # Proposal submission phase
│   ├── debate.py                    # Attack/defense phase
│   └── vote.py                      # Voting phase
│
├── tools/                           # Tool Use (future expansion)
│   ├── __init__.py
│   ├── alliance.py                  # Alliance tools
│   ├── private_message.py           # Private messaging
│   └── spy.py                       # Reconnaissance tools
│
├── data/                            # Runtime data (gitignored)
│   ├── memory_db/                   # ChromaDB persistent storage
│   │   ├── 大阿哥/                  # Each agent's memory
│   │   ├── 二阿哥/
│   │   ├── ... (9 agents)
│   │   └── game_archive/            # Full game history
│   ├── game.db                      # SQLite structured data
│   └── logs/                        # Game logs
│       └── game_20260101.log
│
├── dashboard/                       # Optional: Web dashboard
│   ├── __init__.py
│   ├── server.py                    # Flask server
│   └── templates/
│       └── index.html
│
├── scripts/                         # Utility scripts
│   ├── reset_db.py                  # Reset all data
│   ├── export_game.py               # Export game to JSON
│   └── analyze.py                   # Post-game analysis
│
└── tests/                           # Unit tests
    ├── __init__.py
    ├── test_memory.py
    ├── test_vote_engine.py
    └── test_orchestrator.py