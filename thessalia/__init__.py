"""thessalia — correction assistée de copies papier scannées (ESME).

Modules :
    common            constantes, I/O JSON, conversions mm <-> px, prétraitement image
    template_builder  PDF vierge (WeasyPrint, vectoriel)  -> gabarit JSON
    loader            scan (PDF / images / TIFF multipage) -> liste d'images
    align             fiducials -> homographie -> identification de page -> page redressée
    omr               cases à cocher : raffinement local, taux d'encre, décision
    extract           découpe des zones non-OMR (identité, blancs, cadres de code)
    report            overlays de contrôle, JSON / CSV de sortie
    pipeline          orchestration scan -> copies -> résultats
    grade             application d'un corrigé (optionnel)
"""
__version__ = "0.1.0"
