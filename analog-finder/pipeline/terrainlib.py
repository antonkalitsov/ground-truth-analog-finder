"""Shared terrain statistics used for Earth, Mars and the Moon.

Every world is reduced to the same ground sampling (about 1.85 km per pixel) and the same
window (15 x 15 pixels, about 28 km), so the numbers are directly comparable:

  slope   mean slope in degrees (central differences over a 2-pixel baseline)
  rough   RMS height difference between each pixel and its 5 x 5 neighbourhood mean (m)
  relief  95th minus 5th percentile of elevation inside the window (m)
  elev    mean elevation inside the window (m)

These are the same definitions as web/js/terrain.js (used for the live terrain chips).
"""
import numpy as np

WIN = 15  # window size in pixels


def _box5(z):
    """5x5 box mean with edge replication (2D)."""
    p = np.pad(z, 2, mode="edge")
    c = np.cumsum(np.cumsum(p, axis=0, dtype=np.float64), axis=1)
    c = np.pad(c, ((1, 0), (1, 0)))
    s = c[5:, 5:] - c[:-5, 5:] - c[5:, :-5] + c[:-5, :-5]
    return (s / 25.0).astype(np.float32)


def window_stats(z, valid, dx, dy):
    """Stats for one window. z: 2D float array (with a 2 px margin), valid: bool mask or None."""
    gy, gx = np.gradient(z, dy, dx)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    resid = z - _box5(z)
    core = (slice(2, -2), slice(2, -2))
    zc, sc, rc = z[core], slope[core], resid[core]
    if valid is not None:
        m = valid[core]
        if m.sum() < 0.2 * m.size:
            return None
        zc, sc, rc = zc[m], sc[m], rc[m]
    p5, p95 = np.percentile(zc, [5, 95])
    return dict(slope=float(sc.mean()), rough=float(np.sqrt((rc ** 2).mean())),
                relief=float(p95 - p5), elev=float(zc.mean()))


def equirect_grid_stats(dem, valid, radius_m, cell_px, log=None):
    """Terrain stats on a regular lat/lon cell grid from a global equirectangular DEM.

    dem     2D float32/int16, row 0 = +90 lat, full 360 deg in x
    valid   2D bool (True = use this pixel) or None
    cell_px pixels per output cell (y and x)
    At latitude phi the pixels are block-averaged in x by k = round(1/cos(phi)) so that ground
    pixels stay roughly square, and the window is always WIN x WIN averaged pixels centred on
    the cell (about 28 km on a side when the pixel is about 1.85 km).
    Returns dict of 2D float32 arrays (NaN where there is not enough valid data).
    """
    H, W = dem.shape
    my = np.pi * radius_m / H  # metres per pixel north-south
    ny, nx = H // cell_px, W // cell_px
    out = {k: np.full((ny, nx), np.nan, dtype=np.float32) for k in ("slope", "rough", "relief", "elev", "validfrac")}
    half = WIN // 2
    for i in range(ny):
        rc = i * cell_px + cell_px / 2.0
        lat = 90.0 - rc * 180.0 / H
        coslat = max(np.cos(np.radians(lat)), 1e-3)
        k = int(min(max(1, round(1.0 / coslat)), 48))
        r0 = int(round(rc - WIN / 2.0)) - 2
        r1 = r0 + WIN + 4
        rows = np.clip(np.arange(r0, r1), 0, H - 1)
        Wk = W // k
        strip = dem[rows, :Wk * k].astype(np.float32)
        if k > 1:
            strip = strip.reshape(len(rows), Wk, k).mean(-1)
        if valid is not None:
            vs = valid[rows, :Wk * k].astype(np.float32)
            if k > 1:
                vs = vs.reshape(len(rows), Wk, k).mean(-1)
            vmask = vs >= 0.5
        dx = k * my * coslat  # the x pixel is k source pixels wide
        # wrap in x so windows near the date line are complete
        pad = WIN + 4
        sp = np.concatenate([strip[:, -pad:], strip, strip[:, :pad]], axis=1)
        gy, gx = np.gradient(sp, my, dx)
        slope = np.degrees(np.arctan(np.hypot(gx, gy)))
        resid = sp - _box5(sp)
        core = slice(2, 2 + WIN)
        xc = (np.arange(nx) + 0.5) * cell_px / k
        starts = np.round(xc - WIN / 2.0).astype(int) + pad
        idx = starts[:, None] + np.arange(WIN)[None, :]            # (nx, WIN)
        Z = sp[core][:, idx].transpose(1, 0, 2).reshape(nx, -1)    # (nx, WIN*WIN)
        S = slope[core][:, idx].transpose(1, 0, 2).reshape(nx, -1)
        Rr = resid[core][:, idx].transpose(1, 0, 2).reshape(nx, -1)
        if valid is not None:
            vp = np.concatenate([vmask[:, -pad:], vmask, vmask[:, :pad]], axis=1)
            M = vp[core][:, idx].transpose(1, 0, 2).reshape(nx, -1)
            frac = M.mean(1)
            Zm = np.where(M, Z, np.nan); Sm = np.where(M, S, np.nan); Rm = np.where(M, Rr, np.nan)
            ok = frac >= 0.2
            with np.errstate(all="ignore"):
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    p = np.nanpercentile(Zm[ok], [5, 95], axis=1) if ok.any() else np.zeros((2, 0))
                    out["slope"][i, ok] = np.nanmean(Sm[ok], 1)
                    out["rough"][i, ok] = np.sqrt(np.nanmean(Rm[ok] ** 2, 1))
                    out["relief"][i, ok] = p[1] - p[0]
                    out["elev"][i, ok] = np.nanmean(Zm[ok], 1)
            out["validfrac"][i] = frac
        else:
            p = np.percentile(Z, [5, 95], axis=1)
            out["slope"][i] = S.mean(1)
            out["rough"][i] = np.sqrt((Rr ** 2).mean(1))
            out["relief"][i] = p[1] - p[0]
            out["elev"][i] = Z.mean(1)
            out["validfrac"][i] = 1.0
        if log and i % 100 == 0:
            log(f"row {i}/{ny}")
    return out


def mean_noon_sun_elevation(lat_deg, obliquity_deg, n=720):
    """Annual mean of the noon solar elevation (deg), counting the sun as 0 when below the horizon."""
    lat = np.atleast_1d(np.asarray(lat_deg, dtype=np.float64))
    t = (np.arange(n) + 0.5) / n * 2 * np.pi
    decl = np.degrees(np.arcsin(np.sin(np.radians(obliquity_deg)) * np.sin(t)))
    el = 90.0 - np.abs(lat[..., None] - decl)
    return np.clip(el, 0, 90).mean(-1)
