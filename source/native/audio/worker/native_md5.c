/* ScummVM - Graphic Adventure Engine
 *
 * ScummVM is the legal property of its developers, whose names
 * are too numerous to list here. Please refer to the COPYRIGHT
 * file distributed with this source distribution.
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 */

/*
 * RFC 1321 compliant MD5 implementation,
 * by Christophe Devine <devine(at)cr0.net>
 * this program is licensed under the GPL.
 */

/* Local C adaptation; the digest algorithm is unchanged. */
#include "native_md5.h"
#include <string.h>

static NvU32 nv_get_le32(const NvU8 *p) {
 return (NvU32)p[0] | ((NvU32)p[1] << 8) | ((NvU32)p[2] << 16) | ((NvU32)p[3] << 24);
}
static void nv_put_le32(NvU8 *p, NvU32 n) {
 p[0] = n; p[1] = n >> 8; p[2] = n >> 16; p[3] = n >> 24;
}

#define GET_UINT32(n, b, i)	(n) = nv_get_le32(b + i)
#define PUT_UINT32(n, b, i)	nv_put_le32(b + i, n)

void nv_md5_init(struct NvMd5 *ctx) {
	ctx->total[0] = 0;
	ctx->total[1] = 0;

	ctx->state[0] = 0x67452301;
	ctx->state[1] = 0xEFCDAB89;
	ctx->state[2] = 0x98BADCFE;
	ctx->state[3] = 0x10325476;
}

void nv_md5_process_68000(struct NvMd5 *ctx, const NvU8 data[64]);
#define nv_md5_process nv_md5_process_68000

void nv_md5_update(struct NvMd5 *ctx, const NvU8 *input, NvU32 length) {
	NvU32 left, fill;

	if (!length)
		return;

	left = ctx->total[0] & 0x3F;
	fill = 64 - left;

	ctx->total[0] += length;
	ctx->total[0] &= 0xFFFFFFFF;

	if (ctx->total[0] < length)
		ctx->total[1]++;

	if (left && length >= fill) {
		memcpy((void *)(ctx->buffer + left), (const void *)input, fill);
		nv_md5_process(ctx, ctx->buffer);
		length -= fill;
		input  += fill;
		left = 0;
	}

	while (length >= 64) {
		nv_md5_process(ctx, input);
		length -= 64;
		input  += 64;
	}

	if (length) {
		memcpy((void *)(ctx->buffer + left), (const void *)input, length);
	}
}

static const NvU8 md5_padding[64] = {
	0x80, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
};

void nv_md5_finish(struct NvMd5 *ctx, NvU8 digest[16]) {
	NvU32 last, padn;
	NvU32 high, low;
	NvU8 msglen[8];

	high = (ctx->total[0] >> 29) | (ctx->total[1] << 3);
	low  = (ctx->total[0] <<  3);

	PUT_UINT32(low,  msglen, 0);
	PUT_UINT32(high, msglen, 4);

	last = ctx->total[0] & 0x3F;
	padn = (last < 56) ? (56 - last) : (120 - last);

	nv_md5_update(ctx, md5_padding, padn);
	nv_md5_update(ctx, msglen, 8);

	PUT_UINT32(ctx->state[0], digest,  0);
	PUT_UINT32(ctx->state[1], digest,  4);
	PUT_UINT32(ctx->state[2], digest,  8);
	PUT_UINT32(ctx->state[3], digest, 12);
}


int nv_md5_stream(FILE *stream, NvU8 digest[16]) {
 struct NvMd5 context;
 NvU8 buffer[1024];
 size_t count;
 long position = ftell(stream);
 int result;
 if (position < 0 || fseek(stream, 0, SEEK_SET)) return 0;
 nv_md5_init(&context);
 while ((count = fread(buffer, 1, sizeof(buffer), stream)) != 0)
  nv_md5_update(&context, buffer, count);
 result = !ferror(stream);
 nv_md5_finish(&context, digest);
 clearerr(stream);
 if (fseek(stream, position, SEEK_SET)) result = 0;
 return result;
}
int nv_md5_file(const char *path, NvU8 digest[16]) {
 FILE *stream = fopen(path, "rb");
 int result;
 if (!stream) return 0;
 result = nv_md5_stream(stream, digest);
 if (fclose(stream)) result = 0;
 return result;
}
