/* SPDX-License-Identifier: AGPL-3.0-or-later
 * Copyright (C) 2026 Em Dash Smoker
 * Part of Spectro Maestro. See LICENSE and THIRD-PARTY-NOTICES.md at the root of the skill. */
/* Block-updated biquad in transposed direct form II.
 * Produces what scipy.signal.lfilter gives when it is called block by block with the filter state
 * carried over; it only removes the per-block call overhead. x and y hold n frames of `channels`
 * interleaved samples; b and a hold three coefficients per block with a[0] == 1. */
#include <stddef.h>

void tv_biquad(const double *x, double *y, long n, int channels, const double *b, const double *a,
               long nblocks, long block)
{
    for (int c = 0; c < channels; ++c) {
        double z1 = 0.0, z2 = 0.0;
        for (long k = 0; k < nblocks; ++k) {
            const double b0 = b[3 * k], b1 = b[3 * k + 1], b2 = b[3 * k + 2];
            const double a1 = a[3 * k + 1], a2 = a[3 * k + 2];
            long end = (k + 1) * block;
            if (end > n) end = n;
            for (long i = k * block; i < end; ++i) {
                const double in = x[i * channels + c];
                const double out = b0 * in + z1;
                z1 = b1 * in - a1 * out + z2;
                z2 = b2 * in - a2 * out;
                y[i * channels + c] = out;
            }
        }
    }
}
