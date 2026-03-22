import { NextResponse } from "next/server";
import { GeneratePostSchema } from "@/lib/validations/api";
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

export async function POST(request: Request) {
  try {
    // 1. Parse the JSON body
    const body = await request.json();

    // 2. Validate using Zod
    const validationResult = GeneratePostSchema.safeParse(body);
    
    if (!validationResult.success) {
      return NextResponse.json(
        { error: "Invalid request payload", details: validationResult.error.format() },
        { status: 400 }
      );
    }

    // 3. Retrieve user session/token
    const cookieStore = await cookies();
    const supabase = createServerClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
      {
        cookies: {
          getAll() {
            return cookieStore.getAll();
          },
          setAll(cookiesToSet) {
            try {
              cookiesToSet.forEach(({ name, value, options }) =>
                cookieStore.set(name, value, options)
              );
            } catch (error) {
              // The `setAll` method was called from a Server Component.
              // This can be ignored if you have middleware refreshing user sessions.
            }
          },
        },
      }
    );

    const { data: { session }, error: sessionError } = await supabase.auth.getSession();

    if (sessionError || !session || !session.access_token) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    // 4. Forward to Python backend
    const backendUrl = process.env.BACKEND_API_URL || "http://127.0.0.1:8000";
    const targetUrl = `${backendUrl}/api/generate`;

    const backendResponse = await fetch(targetUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${session.access_token}`,
      },
      body: JSON.stringify(validationResult.data),
    });

    // 5. Return the proxy response
    const responseData = await backendResponse.json().catch(() => null);
    
    return NextResponse.json(responseData || { error: "Failed to parse backend response" }, {
      status: backendResponse.status,
    });

  } catch (error) {
    console.error("Proxy error:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}
