export default function NotFound2() {
  return (
    <div className="flex h-screen items-center justify-center">
      <div className="text-center">
        <h1 className="text-6xl font-bold text-gray-300">404</h1>
        <p className="mt-2 text-gray-500">Page not found</p>
        <a href="/" className="mt-4 inline-block text-blue-500 hover:underline">
          Back to home
        </a>
      </div>
    </div>
  );
}