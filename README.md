# Real Prediction Bot

Telegram football prediction bot running on Solana.

## What It Does

Users fund a wallet, pick 3 correct scores from 20 daily games, and pay an entry fee to submit. All 3 correct scores win the payout. Admin controls game creation and result posting.

## Stack

Python 3.11, python-telegram-bot v21, PostgreSQL, Solana (solders + solana-py), AES-256-GCM encryption

## Setup

1. Copy `.env.example` to `.env` and fill in all values
2. Install dependencies with `pip install -r requirements.txt`
3. Run the bot with `python main.py`

## Commands

Users: /start, /pickgames, /previousresult, /wallet, /referral, /exportwallet, /importwallet

Admin: /addgame, /closegame, /postresult, /listusers, /listgames, /broadcast

## Wallet

Every new user gets an auto-generated Solana wallet on first start. Private keys are AES-256-GCM encrypted before storage. Users can export or import their own wallet at any time.
