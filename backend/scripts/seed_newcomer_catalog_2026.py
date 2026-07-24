from __future__ import annotations

"""Seed the 2026 newcomer candidate catalog.

The script only registers the repositories and marks them as curated candidates.
It does not fabricate GitHub/OpenDigger metrics; run the normal repository
ingestion jobs afterwards to populate scores and evidence.
"""

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.db.init_db import init_db
from app.db.models import RepositoryDataStatus
from app.models import RepoCatalog


NEWCOMER_REPOSITORIES: tuple[tuple[str, str], ...] = (
    # AI / LLM / agents
    ("langgenius/dify", "ai"),
    ("langchain-ai/langchain", "ai"),
    ("langchain-ai/langgraph", "ai"),
    ("run-llama/llama_index", "ai"),
    ("run-llama/llama_deploy", "ai"),
    ("pydantic/pydantic-ai", "ai"),
    ("crewAIInc/crewAI", "ai"),
    ("microsoft/autogen", "ai"),
    ("microsoft/semantic-kernel", "ai"),
    ("google/adk-python", "ai"),
    ("google-gemini/gemini-cli", "ai"),
    ("openai/openai-agents-python", "ai"),
    ("huggingface/smolagents", "ai"),
    ("browser-use/browser-use", "ai"),
    ("mem0ai/mem0", "ai"),
    ("infiniflow/ragflow", "ai"),
    ("BerriAI/litellm", "ai"),
    ("vllm-project/vllm", "ai"),
    ("ollama/ollama", "ai"),
    ("lm-sys/FastChat", "ai"),
    ("open-webui/open-webui", "ai"),
    ("Mintplex-Labs/anything-llm", "ai"),
    ("FlowiseAI/Flowise", "ai"),
    ("langfuse/langfuse", "ai"),
    ("Arize-ai/phoenix", "ai"),
    ("deepset-ai/haystack", "ai"),
    ("modelcontextprotocol/servers", "ai"),
    ("bytedance/deer-flow", "ai"),
    ("microsoft/markitdown", "ai"),
    ("firecrawl/firecrawl", "ai"),
    # Deep learning / training / inference
    ("openai/CLIP", "deep-learning"),
    ("openai/evals", "deep-learning"),
    ("microsoft/DeepSpeed", "deep-learning"),
    ("microsoft/LoRA", "deep-learning"),
    ("microsoft/onnxruntime", "deep-learning"),
    ("facebookresearch/segment-anything", "deep-learning"),
    ("facebookresearch/dinov2", "deep-learning"),
    ("NVlabs/instant-ngp", "deep-learning"),
    ("NVlabs/StyleGAN2-ADA", "deep-learning"),
    ("NVlabs/edm", "deep-learning"),
    ("NVIDIA/NeMo", "deep-learning"),
    ("NVIDIA/TensorRT-LLM", "deep-learning"),
    ("NVIDIA/cuda-python", "deep-learning"),
    ("flashinfer-ai/flashinfer", "deep-learning"),
    ("Dao-AILab/flash-attention", "deep-learning"),
    ("OpenGVLab/InternVL", "deep-learning"),
    ("QwenLM/Qwen", "deep-learning"),
    ("QwenLM/Qwen3", "deep-learning"),
    ("deepseek-ai/DeepGEMM", "deep-learning"),
    ("deepseek-ai/DeepSeek-V3", "deep-learning"),
    ("stability-ai/stablediffusion", "deep-learning"),
    ("CompVis/stable-diffusion", "deep-learning"),
    ("allenai/OLMo", "deep-learning"),
    ("allenai/open-instruct", "deep-learning"),
    ("karpathy/nanoGPT", "deep-learning"),
    ("karpathy/minGPT", "deep-learning"),
    ("karpathy/llm.c", "deep-learning"),
    ("karpathy/autoresearch", "deep-learning"),
    ("EleutherAI/lm-evaluation-harness", "deep-learning"),
    ("huggingface/trl", "deep-learning"),
    # Time series / forecasting
    ("timescale/timescaledb", "time-series"),
    ("influxdata/influxdb", "time-series"),
    ("apache/iotdb", "time-series"),
    ("apache/druid", "time-series"),
    ("apache/tsfile", "time-series"),
    ("facebook/prophet", "time-series"),
    ("Nixtla/neuralforecast", "time-series"),
    ("Nixtla/statsforecast", "time-series"),
    ("Nixtla/mlforecast", "time-series"),
    ("Nixtla/nixtla", "time-series"),
    ("unit8co/darts", "time-series"),
    ("sktime/sktime", "time-series"),
    ("aeon-toolkit/aeon", "time-series"),
    ("jdb78/pytorch-forecasting", "time-series"),
    ("SalesforceAIResearch/uni2ts", "time-series"),
    ("google-research/timesfm", "time-series"),
    ("amazon-science/chronos-forecasting", "time-series"),
    ("ibm-granite/granite-tsfm", "time-series"),
    ("thuml/Time-Series-Library", "time-series"),
    ("time-series-foundation-models/lag-llama", "time-series"),
    # Databases / vector databases / OLAP
    ("postgres/postgres", "database"),
    ("mysql/mysql-server", "database"),
    ("mongodb/mongo", "database"),
    ("redis/redis", "database"),
    ("cockroachdb/cockroach", "database"),
    ("yugabyte/yugabyte-db", "database"),
    ("pingcap/tidb", "database"),
    ("oceanbase/oceanbase", "database"),
    ("clickhouse/clickhouse", "database"),
    ("duckdb/duckdb", "database"),
    ("sqlite/sqlite", "database"),
    ("apache/cassandra", "database"),
    ("apache/calcite", "database"),
    ("apache/iceberg", "database"),
    ("apache/doris", "database"),
    ("apache/pinot", "database"),
    ("starrocks/starrocks", "database"),
    ("materializeinc/materialize", "database"),
    ("questdb/questdb", "database"),
    ("scylladb/scylladb", "database"),
    ("neo4j/neo4j", "database"),
    ("janusgraph/janusgraph", "database"),
    ("arangodb/arangodb", "database"),
    ("milvus-io/milvus", "database"),
    ("qdrant/qdrant", "database"),
    ("chroma-core/chroma", "database"),
    ("pgvector/pgvector", "database"),
    ("lancedb/lancedb", "database"),
    ("surrealdb/surrealdb", "database"),
    ("apache/datafusion", "database"),
    # Frontend / visualization / maps
    ("remix-run/react-router", "visualization"),
    ("remix-run/remix", "visualization"),
    ("withastro/astro", "visualization"),
    ("QwikDev/qwik", "visualization"),
    ("emberjs/ember.js", "visualization"),
    ("lit/lit", "visualization"),
    ("alpinejs/alpine", "visualization"),
    ("htmxorg/htmx", "visualization"),
    ("vuejs/pinia", "visualization"),
    ("vuejs/router", "visualization"),
    ("TanStack/router", "visualization"),
    ("TanStack/table", "visualization"),
    ("TanStack/virtual", "visualization"),
    ("radix-ui/primitives", "visualization"),
    ("shadcn-ui/ui", "visualization"),
    ("tailwindlabs/headlessui", "visualization"),
    ("unovue/reka-ui", "visualization"),
    ("xyflow/xyflow", "visualization"),
    ("pmndrs/react-three-fiber", "visualization"),
    ("pmndrs/drei", "visualization"),
    ("mrdoob/three.js", "visualization"),
    ("maplibre/maplibre-gl-js", "visualization"),
    ("visgl/react-map-gl", "visualization"),
    ("visgl/deck.gl", "visualization"),
    ("apache/echarts", "visualization"),
    ("plotly/plotly.js", "visualization"),
    ("vega/vega", "visualization"),
    ("vega/vega-lite", "visualization"),
    ("observablehq/plot", "visualization"),
    ("antvis/G2", "visualization"),
    # Data engineering / streaming / lakehouse
    ("apache/airflow", "data-engineering"),
    ("dagster-io/dagster", "data-engineering"),
    ("PrefectHQ/prefect", "data-engineering"),
    ("dbt-labs/dbt-core", "data-engineering"),
    ("apache/flink", "data-engineering"),
    ("apache/beam", "data-engineering"),
    ("apache/pulsar", "data-engineering"),
    ("redpanda-data/redpanda", "data-engineering"),
    ("confluentinc/ksql", "data-engineering"),
    ("benthosdev/benthos", "data-engineering"),
    ("meltano/meltano", "data-engineering"),
    ("singer-io/singer", "data-engineering"),
    ("estuary/flow", "data-engineering"),
    ("kestra-io/kestra", "data-engineering"),
    ("dlt-hub/dlt", "data-engineering"),
    ("apache/hudi", "data-engineering"),
    ("delta-io/delta", "data-engineering"),
    ("lakeFS/lakeFS", "data-engineering"),
    ("datahub-project/datahub", "data-engineering"),
    ("OpenLineage/OpenLineage", "data-engineering"),
    # MLOps / serving / observability
    ("kubeflow/kubeflow", "mlops"),
    ("seldonio/seldon-core", "mlops"),
    ("bentoml/BentoML", "mlops"),
    ("DAGsHub/DAGsHub", "mlops"),
    ("wandb/wandb", "mlops"),
    ("iterative/dvc", "mlops"),
    ("triton-inference-server/server", "mlops"),
    ("kserve/kserve", "mlops"),
    ("clearml/clearml", "mlops"),
    ("EvidentlyAI/evidently", "mlops"),
    ("whylogs/whylogs", "mlops"),
    ("NannyML/nannyml", "mlops"),
    ("feast-dev/feast", "mlops"),
    ("flyteorg/flyte", "mlops"),
    ("outerbounds/metaflow", "mlops"),
    ("spotify/luigi", "mlops"),
    ("grafana/loki", "mlops"),
    ("grafana/tempo", "mlops"),
    ("openlit/openlit", "mlops"),
    ("opentelemetry/opentelemetry-collector-contrib", "mlops"),
    # Multimodal / robotics / developer tools
    ("huggingface/lerobot", "ai"),
    ("huggingface/datasets", "ai"),
    ("huggingface/tokenizers", "ai"),
    ("huggingface/safetensors", "ai"),
    ("SYSTRAN/faster-whisper", "ai"),
    ("coqui-ai/TTS", "ai"),
    ("snakers4/silero-vad", "ai"),
    ("pyannote/pyannote-audio", "ai"),
    ("open-mmlab/mmengine", "deep-learning"),
    ("open-mmlab/mmyolo", "deep-learning"),
    ("OpenGVLab/InternVideo2", "deep-learning"),
    ("google-deepmind/mujoco", "ai"),
    ("roboflow/supervision", "ai"),
    ("Farama-Foundation/Gymnasium", "ai"),
    ("Farama-Foundation/Minari", "ai"),
    ("neovim/neovim", "developer-tools"),
    ("astral-sh/uv", "developer-tools"),
    ("astral-sh/ruff", "developer-tools"),
    ("msitarzewski/agency-agents", "developer-tools"),
    ("tirth8205/code-review-graph", "developer-tools"),
)


def seed_catalog(db: Session) -> int:
    seen: set[str] = set()
    for repo, seed_domain in NEWCOMER_REPOSITORIES:
        if repo in seen:
            continue
        seen.add(repo)
        catalog = db.get(RepoCatalog, repo) or RepoCatalog(repo_full_name=repo)
        catalog.seed_domain = seed_domain
        if not catalog.domains:
            catalog.domains = [seed_domain]
        if not catalog.stacks:
            catalog.stacks = []
        if not catalog.tags:
            catalog.tags = []
        db.add(catalog)

        status = db.get(RepositoryDataStatus, repo)
        if status is None:
            status = RepositoryDataStatus(
                repo=repo,
                scope="curated",
                enabled=True,
                opendigger_supported=None,
                sync_status="pending",
                metadata_json={"source": "newcomer-catalog-2026"},
            )
            db.add(status)
        else:
            status.scope = "curated"
            status.enabled = True
            if status.sync_status not in {"ready", "running"}:
                status.sync_status = "pending"
            metadata = dict(status.metadata_json or {})
            metadata["newcomer_catalog"] = "2026"
            status.metadata_json = metadata
    db.commit()
    return len(seen)


def main() -> int:
    init_db()
    with SessionLocal() as db:
        count = seed_catalog(db)
    print({"seeded": count, "total_newcomer_candidates": count})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
