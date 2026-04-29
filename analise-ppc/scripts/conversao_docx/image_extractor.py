"""
ImageExtractor - Módulo de extração de imagens de DOCX

Responsável por extrair imagens de documentos DOCX, suportando:
- Extração direta de imagens bitmap (PNG/JPG) do arquivo ZIP
- Renderização de páginas via MS Word para shapes/drawings vetoriais
- Identificação de páginas por texto para extração contextual

Dependências opcionais:
- docx2pdf: Conversão DOCX→PDF via MS Word (Windows)
- pdf2image: Conversão PDF→PNG via poppler
- pdfplumber: Extração de texto de PDF para busca de páginas
"""

import re
import tempfile
import zipfile
from pathlib import Path
from typing import Optional, Tuple


class ImageExtractor:
    """
    Extrator de imagens de documentos DOCX.

    Suporta dois modos de extração:
    1. Bitmap direto: Extrai imagens embutidas diretamente do ZIP
    2. Renderização: Converte página do DOCX para PNG via Word+PDF

    Uso:
        extractor = ImageExtractor("documento.docx")

        # Extrair bitmap direto
        extractor.extract_bitmap("/word/media/image1.png", Path("output/img.png"))

        # Renderizar página específica
        extractor.render_page_as_image(5, Path("output/page5.png"))

        # Extrair imagem de uma seção específica
        path, method = extractor.extract_section_image(
            section_pattern=r"representa[çc][ãa]o.*gr[áa]fica",
            output_path=Path("output/fluxograma.png")
        )
    """

    def __init__(self, docx_path: Path):
        """
        Inicializa o extrator.

        Args:
            docx_path: Caminho para o arquivo DOCX
        """
        self.docx_path = Path(docx_path)
        if not self.docx_path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {self.docx_path}")

    def extract_bitmap(self, partname: str, output_path: Path) -> Path:
        """
        Extrai imagem bitmap do ZIP do DOCX.

        Args:
            partname: Caminho da imagem no ZIP (ex: "/word/media/image1.png")
            output_path: Caminho de saída para a imagem

        Returns:
            Path do arquivo salvo

        Raises:
            KeyError: Se a imagem não existir no ZIP
        """
        with zipfile.ZipFile(self.docx_path, 'r') as z:
            # Normalizar caminho (remover / inicial se houver)
            zip_path = partname.lstrip('/')
            img_data = z.read(zip_path)

            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(img_data)

            return output_path

    def list_images_in_zip(self) -> list:
        """
        Lista todas as imagens disponíveis no ZIP do DOCX.

        Returns:
            Lista de caminhos de imagens no ZIP
        """
        images = []
        with zipfile.ZipFile(self.docx_path, 'r') as z:
            for name in z.namelist():
                if name.startswith('word/media/'):
                    images.append('/' + name)
        return images

    def render_page_as_image(
        self,
        page_number: int,
        output_path: Path,
        dpi: int = 150
    ) -> Path:
        """
        Renderiza uma página do DOCX como imagem PNG.

        Usa MS Word (via docx2pdf) para converter o documento para PDF,
        depois pdf2image (via poppler) para extrair a página como PNG.

        Args:
            page_number: Número da página (1-indexed)
            output_path: Caminho de saída para a imagem
            dpi: Resolução da imagem (padrão 150)

        Returns:
            Path do arquivo salvo

        Raises:
            ImportError: Se docx2pdf ou pdf2image não estiverem instalados
            ValueError: Se a página não puder ser renderizada
        """
        try:
            from docx2pdf import convert
        except ImportError:
            raise ImportError(
                "docx2pdf é necessário para renderização. "
                "Instale com: pip install docx2pdf"
            )

        try:
            from pdf2image import convert_from_path
        except ImportError:
            raise ImportError(
                "pdf2image é necessário para renderização. "
                "Instale com: pip install pdf2image\n"
                "Também requer poppler instalado e no PATH."
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # 1. DOCX → PDF via MS Word
            pdf_path = tmpdir / "temp.pdf"
            convert(str(self.docx_path), str(pdf_path))

            # 2. PDF → PNG (página específica)
            images = convert_from_path(
                str(pdf_path),
                dpi=dpi,
                first_page=page_number,
                last_page=page_number
            )

            if images:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                images[0].save(str(output_path), 'PNG')
                return output_path

        raise ValueError(f"Não foi possível renderizar página {page_number}")

    def _is_toc_page(self, text: str, threshold: int = 10) -> bool:
        """
        Detecta se uma página é um Sumário/Table of Contents.

        Páginas de sumário tipicamente têm muitas linhas com formato:
        "1.1 Título da Seção ... 5" ou "1.1 Título da Seção\t5"

        Args:
            text: Texto extraído da página
            threshold: Número mínimo de entradas numeradas para considerar TOC

        Returns:
            True se a página parece ser um sumário
        """
        # Padrão para linhas de sumário: número.número seguido de texto e número de página
        # Exemplos: "1.1 Introdução\t5", "5.12 REPRESENTAÇÃO GRÁFICA ... 84"
        toc_pattern = r'^\s*\d+\.\d+.*\d+\s*$'
        lines = text.split('\n')
        toc_entries = sum(1 for line in lines if re.match(toc_pattern, line.strip()))
        return toc_entries >= threshold

    def find_page_with_text(
        self,
        search_text: str,
        skip_toc: bool = True
    ) -> Optional[int]:
        """
        Encontra o número da página que contém determinado texto.

        Usa pdfplumber para buscar texto no PDF convertido.

        Args:
            search_text: Texto ou padrão regex para buscar
            skip_toc: Se True, ignora páginas de sumário (default: True)

        Returns:
            Número da página (1-indexed) ou None se não encontrado

        Raises:
            ImportError: Se as dependências não estiverem instaladas
        """
        try:
            from docx2pdf import convert
        except ImportError:
            raise ImportError(
                "docx2pdf é necessário. Instale com: pip install docx2pdf"
            )

        try:
            import pdfplumber
        except ImportError:
            raise ImportError(
                "pdfplumber é necessário para busca de páginas. "
                "Instale com: pip install pdfplumber"
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            pdf_path = tmpdir / "temp.pdf"
            convert(str(self.docx_path), str(pdf_path))

            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text() or ""
                    if re.search(search_text, text, re.IGNORECASE):
                        # Pular páginas de sumário se skip_toc=True
                        if skip_toc and self._is_toc_page(text):
                            continue
                        return i

        return None

    def extract_section_image(
        self,
        section_pattern: str,
        output_path: Path,
        has_bitmap: bool = False,
        bitmap_partname: Optional[str] = None,
        dpi: int = 150
    ) -> Tuple[Path, str]:
        """
        Extrai imagem de uma seção específica do documento.

        Estratégia:
        1. Se há bitmap na seção (has_bitmap=True), extrai diretamente do ZIP
        2. Se há apenas shapes/drawings, renderiza a página do PDF

        Args:
            section_pattern: Padrão regex para encontrar a seção no texto
            output_path: Caminho de saída para a imagem
            has_bitmap: Se True, há uma imagem bitmap na seção
            bitmap_partname: Caminho da imagem bitmap no ZIP
            dpi: Resolução para renderização (se necessário)

        Returns:
            Tuple[Path, str]: (caminho da imagem salva, método usado)
            - método: "bitmap" se extraído do ZIP, "rendered" se renderizado

        Raises:
            ValueError: Se a seção não for encontrada
        """
        # 1. Se há bitmap, extrair diretamente
        if has_bitmap and bitmap_partname:
            self.extract_bitmap(bitmap_partname, output_path)
            return output_path, "bitmap"

        # 2. Fallback: renderizar página que contém a seção
        page_num = self.find_page_with_text(section_pattern)
        if page_num:
            self.render_page_as_image(page_num, output_path, dpi=dpi)
            return output_path, "rendered"

        raise ValueError(f"Seção com padrão '{section_pattern}' não encontrada no documento")

    def check_dependencies(self) -> dict:
        """
        Verifica se as dependências opcionais estão instaladas.

        Returns:
            Dict com status de cada dependência
        """
        status = {
            'docx2pdf': False,
            'pdf2image': False,
            'pdfplumber': False,
            'can_render': False,
        }

        try:
            import docx2pdf
            status['docx2pdf'] = True
        except ImportError:
            pass

        try:
            import pdf2image
            status['pdf2image'] = True
        except ImportError:
            pass

        try:
            import pdfplumber
            status['pdfplumber'] = True
        except ImportError:
            pass

        # Pode renderizar se tem docx2pdf E pdf2image
        status['can_render'] = status['docx2pdf'] and status['pdf2image']

        return status
