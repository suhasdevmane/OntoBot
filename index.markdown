---
layout: home
title: OntoBot
description: End-to-end platform for human–building conversation in natural language.
---

# OntoBot Documentation

OntoBot is a production-ready, end-to-end platform for human–building conversation in natural language. It combines Rasa 3.6.12, analytics microservices, knowledge stores (SQL/SPARQL/NoSQL), and optional AI helpers to turn sensor and ontology data into user-friendly insights.

## 🏢 Building-Specific Documentation

Explore documentation for each of our three smart buildings:

- [**Building 1 - ABACWS**](/docs/building1_abacws/) - Real university testbed with 680 sensors, MySQL, Indoor Environmental Quality (IEQ) monitoring
- [**Building 2 - Office Building**](/docs/building2_office/) - Synthetic commercial building with 329 sensors, TimescaleDB, HVAC optimization
- [**Building 3 - Data Center**](/docs/building3_datacenter/) - Critical infrastructure with 597 sensors, Cassandra, cooling & power monitoring

**Total**: 1,606 sensors across all buildings

## 📚 Getting Started

### Quick Start & Installation

- [**Quick Start Guide**](/docs/quickstart/) - Get OntoBot running in 30 minutes
- [**Installation Guide**](/docs/installation/) - Detailed setup instructions
- [**Architecture Overview**](/docs/architecture/) - System design and components

### Core Documentation

- [**Introduction**](/docs/introduction/) - What is OntoBot and key features
- [**Usage Guide**](/docs/usage/) - How to interact with the system
- [**Services Overview**](/docs/services/) - All 8+ microservices explained

## 🔧 Technical Documentation

### Database Integration

- [**Database Integration Guide**](/docs/database_integration/) - MySQL, TimescaleDB, and Cassandra implementation guides
  - MySQL 8.0 (Building 1) - Traditional relational database
  - TimescaleDB 2.11 (Building 2) - Time-series optimized PostgreSQL
  - Cassandra 4.1 (Building 3) - Distributed NoSQL for high availability

### Advanced Topics

- [**Backend Services**](/docs/backend_services/) - All 8 services with API references
- [**Frontend UI Guide**](/docs/frontend_ui/) - Complete UI reference and keyboard shortcuts
- [**T5 Training Guide**](/docs/t5_training_guide/) - NL2SPARQL model training workflow
- [**Multi-Building Support**](/docs/multi_building/) - Switching buildings and portability
- [**Analytics API Reference**](/docs/analytics_api/) - 30+ analytics types with examples
- [**Data & Payloads**](/docs/data_payloads/) - Request/response formats
- [**Customization Guide**](/docs/customization/) - Extending OntoBot for your needs

## 🐛 Support & Troubleshooting

- [**Troubleshooting & FAQ**](/docs/troubleshooting/) - Common issues and solutions
  - Docker & Compose issues
  - Database problems (MySQL, TimescaleDB, Cassandra)
  - Service health issues
  - Performance optimization
  - Development workflow
- [**Testing & Operations**](/docs/testing_ops/) - Testing procedures and operational best practices

## 📊 Features by Building

| Feature | Building 1 | Building 2 | Building 3 |
|---------|------------|------------|------------|
| **Sensors** | 680 (IEQ) | 329 (HVAC) | 597 (Critical) |
| **Database** | MySQL 8.0 | TimescaleDB 2.11 | Cassandra 4.1 |
| **Focus** | Air Quality | Thermal Comfort | Cooling & Power |
| **Type** | Real Testbed | Synthetic Office | Synthetic DC |
| **Special Features** | CO2, PM, TVOC | AHUs, Chillers, VAV | CRAC, UPS, PDU |

## 🚀 Technology Stack

- **Conversational AI**: Rasa 3.6.12
- **Backend**: Python 3.10, Flask, FastAPI
- **Frontend**: React 18+
- **Databases**: MySQL 8.0, TimescaleDB 2.11, Cassandra 4.1
- **Knowledge Graph**: Apache Jena Fuseki, Brick Schema 1.3
- **Analytics**: 30+ analytics types (forecasting, anomaly detection, etc.)
- **NL2SPARQL**: T5-based transformer model
- **LLM**: Mistral via Ollama for summarization
- **Containerization**: Docker & Docker Compose

## 📖 Documentation Index

### By Category

**Buildings & Infrastructure:**
- [Building 1 - ABACWS (Real Testbed)](/docs/building1_abacws/)
- [Building 2 - Office (HVAC Focus)](/docs/building2_office/)
- [Building 3 - Data Center (Critical Infrastructure)](/docs/building3_datacenter/)
- [Multi-Building Support](/docs/multi_building/)

**Database & Integration:**
- [Database Integration Guide](/docs/database_integration/)
- [Data & Payloads](/docs/data_payloads/)

**Services & APIs:**
- [Backend Services](/docs/backend_services/)
- [Analytics API Reference](/docs/analytics_api/)
- [Services Overview](/docs/services/)

**User Interfaces:**
- [Frontend UI Guide](/docs/frontend_ui/)
- [T5 Training GUI](/docs/t5_training_guide/)

**Development & Operations:**
- [Quick Start](/docs/quickstart/)
- [Installation](/docs/installation/)
- [Architecture](/docs/architecture/)
- [Usage](/docs/usage/)
- [Customization](/docs/customization/)
- [Testing & Operations](/docs/testing_ops/)
- [Troubleshooting & FAQ](/docs/troubleshooting/)

## 🎓 Research & Academic Use

OntoBot is designed for both production deployment and academic research:

- **Real-world testbed data** (Building 1 - ABACWS at Cardiff University)
- **Synthetic building scenarios** (Buildings 2 & 3 for controlled experiments)
- **Multiple database technologies** for comparative studies
- **Open-source** and extensively documented
- **Reproducible experiments** with Docker Compose

## 🤝 Contributing

OntoBot is actively developed and welcomes contributions:

- **GitHub Repository**: [suhasdevmane/OntoBot](https://github.com/suhasdevmane/OntoBot)
- **Issues & Bug Reports**: [GitHub Issues](https://github.com/suhasdevmane/OntoBot/issues)
- **Documentation**: This site!

## 📄 License

OntoBot is released under the **MIT License**. See the [LICENSE](https://github.com/suhasdevmane/OntoBot/blob/main/LICENSE) file for details.

---

## 🔗 External Resources

- **Rasa Documentation**: [rasa.com/docs](https://rasa.com/docs/)
- **Brick Schema**: [brickschema.org](https://brickschema.org/)
- **TimescaleDB**: [docs.timescale.com](https://docs.timescale.com/)
- **Cassandra**: [cassandra.apache.org](https://cassandra.apache.org/)
- **Docker**: [docs.docker.com](https://docs.docker.com/)

---

**Ready to get started?** Check out the [Quick Start Guide](/docs/quickstart/) to get OntoBot running in 30 minutes!
