// Supabase Configuration
// These keys are safe to expose - Row Level Security protects the data

const SUPABASE_URL = "https://jrdrwjctazuynvzlbgth.supabase.co";
const SUPABASE_ANON_KEY = "sb_publishable_nXSHLK63UxIF0AyZUpSAxA_h5iU45gd";

const supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
