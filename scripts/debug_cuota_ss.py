from pathlib import Path
from src.services.scanner import InvoiceScanner
from src.db.repositories import InvoiceRepository
from src.utils.hashing import sha256_file


PDF_PATH = Path(r"C:\Users\ignac\Downloads\1T26\1T 26\CUOTA SS\MARZO 446.62€.pdf")


class DebugRepository(InvoiceRepository):
    def upsert(self, invoice):
        # Print required fields just before persistence
        print("--- UPsert debug (just before DB) ---")
        print("archivo:", invoice.archivo)
        print("file_hash:", invoice.hash_archivo)
        print("parser_usado:", invoice.parser_usado)
        print("fecha_factura:", invoice.fecha_factura)
        print("numero_factura:", invoice.numero_factura)
        print("total:", invoice.total)
        print("tipo_documento:", invoice.tipo_documento)
        print("-------------------------------------")
        return super().upsert(invoice)


def run_once(scanner: InvoiceScanner, pdf_path: Path):
    file_hash = sha256_file(pdf_path)
    result = scanner._process_file(
        pdf_path=pdf_path,
        file_hash=file_hash,
        parser_name=None,
        folder_origin=pdf_path.parent.name,
    )

    # matched_parsers comes back in the result dict
    matched = result.get("matched_parsers")
    # parser finally selected can be inferred from the upsert print above (invoice.parser_usado)
    print("matched_parsers:", matched)
    return result


def main():
    if not PDF_PATH.exists():
        print("ERROR: PDF not found:", PDF_PATH)
        return

    debug_repo = DebugRepository()
    scanner = InvoiceScanner(repository=debug_repo)

    print("=== Run 1 ===")
    res1 = run_once(scanner, PDF_PATH)

    print("=== Run 2 ===")
    res2 = run_once(scanner, PDF_PATH)

    # Summarize
    print("=== Summary ===")
    print("run1 result:", {k: v for k, v in res1.items() if k in ("document_type", "matched_parsers")})
    print("run2 result:", {k: v for k, v in res2.items() if k in ("document_type", "matched_parsers")})


if __name__ == "__main__":
    main()
