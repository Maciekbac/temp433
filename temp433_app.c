/* Copyright 2026 Maciekbac
 * https://github.com/Maciekbac
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 *     Unless required by applicable law or agreed to in writing, software
 *     distributed under the License is distributed on an "AS IS" BASIS,
 *     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *     See the License for the specific language governing permissions and
 *     limitations under the License.
 */

/*
 * Temp 433 - 433 MHz temperature sensor receiver overlay (work in progress).
 *
 * Skeleton: shows the title, EXIT quits.
 */

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include "app_api.h"

#define TICK_MS      40u
#define REFRESH_MS 1000u        /* battery refresh while nothing changes */

/* All the state in one struct. */
struct globals {
    uint8_t previousKey;
    bool running, saverActive, dirty;
    uint32_t drawnAt;
    const app_api_t *api;
};
static struct globals g;
#define A (g.api)

static void render(void)
{
    A->display_clear();
    A->status_clear();
    A->draw_battery();
    A->print_bold("Temp 433", 0, 127, 2);
    A->print_normal("Work in progress", 0, 127, 4);
}

static void poll_key(void)
{
    uint8_t key = A->get_key();
    if (key == APP_KEY_SAVER) {
        g.saverActive = true;
        g.previousKey = APP_KEY_INVALID;
        return;
    }
    if (key == APP_KEY_WAKE || key == APP_KEY_PTT) {
        g.saverActive = false;
        g.dirty = true;
        key = APP_KEY_INVALID;
    }
    if (key != g.previousKey && key != APP_KEY_INVALID) {
        A->backlight_on();
        if (key == APP_KEY_EXIT)
            g.running = false;
    }
    g.previousKey = key;
}

__attribute__((section(".text.entry"), used))
void app_main(const app_api_t *api)
{
    A = api;
    g.previousKey = A->get_key();    /* a key still held from the launcher is ignored */
    g.running = true;
    g.dirty = true;
    A->backlight_on();

    while (g.running) {
        poll_key();
        if (!g.running)
            break;

        const uint32_t now = A->ticks_ms();
        if (!g.saverActive && (g.dirty || now - g.drawnAt >= REFRESH_MS)) {
            render();
            A->blit_status();
            A->blit_full();
            g.dirty = false;
            g.drawnAt = now;
        }
        A->battery_sample();
        A->backlight_update();
        A->delay_ms(TICK_MS);
    }
}
