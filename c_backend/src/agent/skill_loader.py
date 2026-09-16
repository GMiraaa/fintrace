from pathlib import Path

SKILL_REFERENCE_FILES = (
    "references/event-identification.md",
    "references/evidence-and-uncertainty.md",
)

PDF_EXTRACTION_FILES = ("SKILL.md",)


def load_corporate_actions_skill(skill_directory: str | Path) -> str:
    return _load_skill_files(
        skill_directory,
        ("SKILL.md", *SKILL_REFERENCE_FILES),
    )


def load_project_agent_skills(repository_root: str | Path) -> str:
    root = Path(repository_root)
    corporate_actions = load_corporate_actions_skill(
        root / "d_skills/corporate_actions"
    )
    pdf_extraction = _load_skill_files(
        root / ".skills/b_backend_skills/.agents/skills/pdf-extraction",
        PDF_EXTRACTION_FILES,
    )
    return (
        "# Skill de domínio: eventos corporativos\n\n"
        f"{corporate_actions}\n\n"
        "# Skill complementar: extração de PDFs\n\n"
        "Use este conteúdo para interpretar texto, tabelas e estrutura de PDFs. "
        "O backend já executou a leitura nativa e o OCR. Quando necessário, use "
        "as tools de pdfplumber disponibilizadas pelo FinTrace.\n\n"
        f"{pdf_extraction}\n\n"
        "# Restrições de integração do FinTrace\n\n"
        "A skill de PDF é conhecimento complementar. Você não possui acesso genérico "
        "ao filesystem, execução de código ou ferramentas MCP. O acesso ao PDF atual "
        "ocorre exclusivamente pelas function callings vinculadas pelo backend. "
        "Priorize o texto normalizado, cite a página e respeite o schema de resposta "
        "do FinTrace."
    )


def _load_skill_files(
    skill_directory: str | Path,
    files: tuple[str, ...],
) -> str:
    directory = Path(skill_directory)
    sections = []
    for relative_path in files:
        path = directory / relative_path
        if not path.is_file():
            raise FileNotFoundError(f"required skill file not found: {path}")
        sections.append(f"## {relative_path}\n\n{path.read_text(encoding='utf-8')}")
    return "\n\n".join(sections)
