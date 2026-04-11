"""
core/template_aligner.py

Allineamento foto preprocessata al template PDF usando SIFT + ECC.

Strategia (ottimizzata per velocità):
1. SIFT su immagine ridotta (800px width) per trovare homography veloce
2. FLANN knnMatch + Lowe's ratio test (0.75)
3. RANSAC homography → scalata a full-res
4. Warp full-res con homography
5. ECC sub-pixel refinement a full-res
6. Fallback AKAZE se SIFT non trova abbastanza match

SIFT: 128-dim float descriptors, migliore per form stampati
ECC: sub-pixel refinement (usato in Accusoft FormFix, 2px accuracy)
Tutto in opencv-contrib-python, ZERO dipendenze aggiuntive.
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Tuple, Dict
import logging

logger = logging.getLogger(__name__)

# Larghezza per SIFT matching (ridotta per velocità, sufficiente per features)
_MATCH_WIDTH = 800


class TemplateAligner:
    """Allinea foto di questionari CBCL al template PDF di riferimento."""

    # Soglia minima di matches per accettare alignment con maschera.
    # Se sotto questa soglia, riprova senza maschera con piu features.
    _MIN_MATCHES_MASKED = 50

    def __init__(self):
        self._references: Dict[str, np.ndarray] = {}           # full-res
        self._ref_small: Dict[str, np.ndarray] = {}             # ridotta
        self._ref_keypoints: Dict[str, tuple] = {}              # (kp, des) cached con maschera
        self._ref_keypoints_nomask: Dict[str, tuple] = {}       # (kp, des) cached senza maschera
        self._scale_factors: Dict[str, float] = {}              # fattore scala
        self._sift = cv2.SIFT_create(nfeatures=2000)
        self._sift_big = cv2.SIFT_create(nfeatures=5000)
        self._flann = cv2.FlannBasedMatcher(
            dict(algorithm=1, trees=5),
            dict(checks=50)
        )

    def load_reference(self, page_key: str):
        """
        Carica immagine di riferimento da templates/.

        Args:
            page_key: "page_4" o "page_5"

        Raises:
            FileNotFoundError se il file non esiste
        """
        templates_dir = Path(__file__).parent.parent / "templates"
        ref_path = templates_dir / f"cbcl_{page_key}_ref.png"

        if not ref_path.exists():
            raise FileNotFoundError(
                f"Riferimento non trovato: {ref_path}. "
                "Eseguire: python scripts/generate_references.py"
            )

        ref = cv2.imread(str(ref_path), cv2.IMREAD_GRAYSCALE)
        if ref is None:
            raise FileNotFoundError(f"Impossibile leggere {ref_path}")

        self._references[page_key] = ref

        # Crea versione ridotta per SIFT matching
        h, w = ref.shape
        scale = _MATCH_WIDTH / w
        ref_small = cv2.resize(ref, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        self._ref_small[page_key] = ref_small
        self._scale_factors[page_key] = scale

        # Pre-calcola keypoints sulla versione ridotta (con maschera)
        sh, sw = ref_small.shape
        mask = self._build_structural_mask(sh, sw)
        kp, des = self._sift.detectAndCompute(ref_small, mask)
        self._ref_keypoints[page_key] = (kp, des)

        # Anche senza maschera con piu features (fallback per foto difficili)
        kp_nm, des_nm = self._sift_big.detectAndCompute(ref_small, None)
        self._ref_keypoints_nomask[page_key] = (kp_nm, des_nm)

        logger.info(f"Reference caricato: {page_key} ({w}x{h}, {len(kp)} kp masked, {len(kp_nm)} kp nomask)")

    def align(self, gray: np.ndarray, page_key: str) -> Tuple[np.ndarray, dict]:
        """
        Allinea la foto al template di riferimento.
        Seed fisso per RANSAC deterministico (risultati riproducibili).

        Args:
            gray: immagine grayscale già perspective-corrected
            page_key: "page_4" o "page_5"

        Returns:
            (immagine_allineata, info_dict)
        """
        info = {
            "method": None,
            "good_matches": 0,
            "inliers": 0,
            "ecc_success": False,
            "aligned": False,
        }

        if page_key not in self._references:
            logger.warning(f"Reference {page_key} non caricato, skip alignment")
            return gray, info

        reference = self._references[page_key]

        # Resize gray to match reference if needed
        if gray.shape != reference.shape:
            gray = cv2.resize(gray, (reference.shape[1], reference.shape[0]))

        h, w = gray.shape
        scale = self._scale_factors[page_key]

        # Ridimensiona query per SIFT matching
        gray_small = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        sh, sw = gray_small.shape
        mask_small = self._build_structural_mask(sh, sw)

        # --- Strategia 1: SIFT con maschera strutturale ---
        H_small, good_n, inliers = self._try_sift_cached(page_key, gray_small, mask_small)
        if H_small is not None and good_n >= self._MIN_MATCHES_MASKED:
            H = self._scale_homography(H_small, scale)
            warped = cv2.warpPerspective(gray, H, (w, h))
            info.update(method="sift", good_matches=good_n, inliers=inliers, aligned=True)
            aligned, ecc_ok = self._ecc_refine(reference, warped)
            info["ecc_success"] = ecc_ok
            aligned = self._multi_region_ecc(aligned, reference)
            return aligned, info

        # --- Strategia 1b: SIFT senza maschera, piu features (foto difficili) ---
        # Quando la maschera e troppo restrittiva (angolo/illuminazione diversi)
        best_masked = (H_small, good_n, inliers)  # salva risultato masked
        H_nm, good_nm, inliers_nm = self._try_sift_nomask(page_key, gray_small)

        # Raccogli candidati e scegli il migliore per diff col reference
        candidates = []
        diff_noalign = cv2.absdiff(reference, gray).mean()

        if best_masked[0] is not None:
            H_m = self._scale_homography(best_masked[0], scale)
            w_m = cv2.warpPerspective(gray, H_m, (w, h))
            d_m = cv2.absdiff(reference, w_m).mean()
            candidates.append(('sift', w_m, d_m, best_masked[1], best_masked[2]))

        if H_nm is not None:
            H_n = self._scale_homography(H_nm, scale)
            w_n = cv2.warpPerspective(gray, H_n, (w, h))
            d_n = cv2.absdiff(reference, w_n).mean()
            candidates.append(('sift_nomask', w_n, d_n, good_nm, inliers_nm))

        if candidates:
            # Scegli il candidato con diff minore, ma solo se migliora rispetto a no-alignment
            best = min(candidates, key=lambda x: x[2])
            if best[2] < diff_noalign:
                warped = best[1]
                info.update(method=best[0], good_matches=best[3],
                            inliers=best[4], aligned=True)
                aligned, ecc_ok = self._ecc_refine(reference, warped)
                info["ecc_success"] = ecc_ok
                aligned = self._multi_region_ecc(aligned, reference)
                return aligned, info

        # --- Strategia 2: AKAZE fallback ---
        ref_small = self._ref_small[page_key]
        H_small, good_n, inliers = self._try_akaze(ref_small, gray_small, mask_small)
        if H_small is not None:
            H = self._scale_homography(H_small, scale)
            warped = cv2.warpPerspective(gray, H, (w, h))
            info.update(method="akaze", good_matches=good_n, inliers=inliers, aligned=True)
            aligned, ecc_ok = self._ecc_refine(reference, warped)
            info["ecc_success"] = ecc_ok
            aligned = self._multi_region_ecc(aligned, reference)
            return aligned, info

        # Nessun match sufficiente
        info.update(good_matches=good_n, inliers=inliers)
        logger.warning(f"Alignment fallito per {page_key}: matches={good_n}, inliers={inliers}")
        return gray, info

    @staticmethod
    def _scale_homography(H_small: np.ndarray, scale: float) -> np.ndarray:
        """Scala una homography da coordinate ridotte a full-res."""
        S = np.array([[1/scale, 0, 0], [0, 1/scale, 0], [0, 0, 1]], dtype=np.float64)
        S_inv = np.array([[scale, 0, 0], [0, scale, 0], [0, 0, 1]], dtype=np.float64)
        return S @ H_small @ S_inv

    def _build_structural_mask(self, h: int, w: int) -> np.ndarray:
        """Maschera che evidenzia aree stampate stabili."""
        mask = np.zeros((h, w), dtype=np.uint8)
        mask[0:int(h * 0.22), :] = 255                      # header
        mask[int(h * 0.88):h, :] = 255                       # footer
        mask[:, 0:int(w * 0.06)] = 255                       # margine sinistro
        mask[:, int(w * 0.46):int(w * 0.55)] = 255           # divisore centrale
        mask[:, int(w * 0.94):] = 255                        # margine destro
        return mask

    def _try_sift_nomask(self, page_key, gray_small):
        """SIFT senza maschera con piu features — fallback per foto difficili."""
        if page_key not in self._ref_keypoints_nomask:
            return None, 0, 0
        kp1, des1 = self._ref_keypoints_nomask[page_key]
        kp2, des2 = self._sift_big.detectAndCompute(gray_small, None)

        if des1 is None or des2 is None or len(kp1) < 10 or len(kp2) < 10:
            return None, 0, 0

        raw_matches = self._flann.knnMatch(des1, des2, k=2)
        good = [m for m, n in raw_matches if m.distance < 0.75 * n.distance]

        if len(good) < 8:
            return None, len(good), 0

        src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)

        try:
            H, mask_h = cv2.findHomography(dst_pts, src_pts, cv2.USAC_MAGSAC, 3.0)
        except (cv2.error, AttributeError):
            H, mask_h = cv2.findHomography(dst_pts, src_pts, cv2.RANSAC, 3.0)

        inliers = int(mask_h.ravel().sum()) if mask_h is not None else 0
        if H is None or inliers < 6:
            return None, len(good), inliers

        det = np.linalg.det(H[:2, :2])
        if det < 0.3 or det > 3.0:
            return None, len(good), inliers

        return H, len(good), inliers

    def _try_sift_cached(self, page_key, gray_small, mask):
        """SIFT con keypoints reference cached."""
        kp1, des1 = self._ref_keypoints[page_key]
        kp2, des2 = self._sift.detectAndCompute(gray_small, mask)

        if des1 is None or des2 is None or len(kp1) < 10 or len(kp2) < 10:
            return None, 0, 0

        raw_matches = self._flann.knnMatch(des1, des2, k=2)
        good = [m for m, n in raw_matches if m.distance < 0.75 * n.distance]

        if len(good) < 8:
            return None, len(good), 0

        src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)

        try:
            H, mask_h = cv2.findHomography(dst_pts, src_pts, cv2.USAC_MAGSAC, 3.0)
        except (cv2.error, AttributeError):
            H, mask_h = cv2.findHomography(dst_pts, src_pts, cv2.RANSAC, 3.0)

        inliers = int(mask_h.ravel().sum()) if mask_h is not None else 0
        if H is None or inliers < 6:
            return None, len(good), inliers

        det = np.linalg.det(H[:2, :2])
        if det < 0.3 or det > 3.0:
            return None, len(good), inliers

        return H, len(good), inliers

    def _try_akaze(self, template_small, gray_small, mask):
        """AKAZE fallback su immagini ridotte."""
        akaze = cv2.AKAZE_create()
        bf = cv2.BFMatcher(cv2.NORM_HAMMING)

        kp1, des1 = akaze.detectAndCompute(template_small, mask)
        kp2, des2 = akaze.detectAndCompute(gray_small, mask)

        if des1 is None or des2 is None or len(kp1) < 10 or len(kp2) < 10:
            return None, 0, 0

        raw_matches = bf.knnMatch(des1, des2, k=2)
        good = [m for m, n in raw_matches if m.distance < 0.75 * n.distance]

        if len(good) < 8:
            return None, len(good), 0

        src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)

        try:
            H, mask_h = cv2.findHomography(dst_pts, src_pts, cv2.USAC_MAGSAC, 3.0)
        except (cv2.error, AttributeError):
            H, mask_h = cv2.findHomography(dst_pts, src_pts, cv2.RANSAC, 3.0)

        inliers = int(mask_h.ravel().sum()) if mask_h is not None else 0
        if H is None or inliers < 6:
            return None, len(good), inliers

        det = np.linalg.det(H[:2, :2])
        if det < 0.3 or det > 3.0:
            return None, len(good), inliers

        return H, len(good), inliers

    def _multi_region_ecc(self, src: np.ndarray, reference: np.ndarray,
                          grid_rows: int = 4, grid_cols: int = 2) -> np.ndarray:
        """
        Multi-Region ECC: divide l'immagine in una griglia NxM e applica
        ECC locale a ciascuna regione per correggere distorsione prospettica locale.

        Una singola homography globale non corregge la distorsione locale
        (es. foglio curvo o prospettiva non corretta). Dividendo in regioni
        e allineando ciascuna localmente, compensiamo lo shift variabile.

        Griglia 4x2 = 8 regioni, ~700ms totale su 2480x3509.
        """
        h, w = src.shape
        result = src.copy()

        for r in range(grid_rows):
            for c in range(grid_cols):
                y1 = int(r * h / grid_rows)
                y2 = int((r + 1) * h / grid_rows)
                x1 = int(c * w / grid_cols)
                x2 = int((c + 1) * w / grid_cols)

                # Margine overlap per contesto
                margin = 30
                y1m = max(0, y1 - margin)
                y2m = min(h, y2 + margin)
                x1m = max(0, x1 - margin)
                x2m = min(w, x2 + margin)

                src_region = src[y1m:y2m, x1m:x2m]
                ref_region = reference[y1m:y2m, x1m:x2m]

                # ECC su versione ridotta per velocita
                scale = 0.5
                src_small = cv2.resize(src_region, None, fx=scale, fy=scale)
                ref_small = cv2.resize(ref_region, None, fx=scale, fy=scale)

                try:
                    warp_matrix = np.eye(2, 3, dtype=np.float32)
                    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 1e-3)
                    _, warp_matrix = cv2.findTransformECC(
                        ref_small, src_small, warp_matrix,
                        cv2.MOTION_EUCLIDEAN, criteria
                    )
                    # Scala traslazione a full-res
                    warp_matrix[0, 2] /= scale
                    warp_matrix[1, 2] /= scale

                    inner = src[y1:y2, x1:x2]
                    aligned_inner = cv2.warpAffine(
                        inner, warp_matrix, (x2 - x1, y2 - y1),
                        flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP,
                        borderMode=cv2.BORDER_REPLICATE
                    )
                    result[y1:y2, x1:x2] = aligned_inner
                except cv2.error:
                    pass  # ECC non converge su questa regione, mantieni originale

        return result

    def _ecc_refine(self, reference: np.ndarray, warped: np.ndarray) -> Tuple[np.ndarray, bool]:
        """
        ECC sub-pixel refinement.
        Eseguito su immagine ridotta per velocità, poi applicato a full-res.
        """
        try:
            h, w = warped.shape
            # ECC su immagine ridotta (molto più veloce)
            ecc_width = 600
            scale = ecc_width / w
            ref_small = cv2.resize(reference, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            warp_small = cv2.resize(warped, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

            warp_matrix = np.eye(2, 3, dtype=np.float32)
            criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 1e-3)
            _, warp_matrix = cv2.findTransformECC(
                ref_small, warp_small, warp_matrix,
                cv2.MOTION_EUCLIDEAN, criteria
            )

            # Scala traslazione da coordinate ridotte a full-res
            warp_matrix[0, 2] /= scale  # tx
            warp_matrix[1, 2] /= scale  # ty

            aligned = cv2.warpAffine(warped, warp_matrix, (w, h),
                                     flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP)
            return aligned, True
        except cv2.error as e:
            logger.warning(f"ECC refinement fallito: {e}")
            return warped, False
