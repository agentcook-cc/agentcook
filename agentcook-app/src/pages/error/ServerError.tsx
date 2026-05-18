export default function ServerError() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center text-center">
      <h1 className="text-7xl font-extrabold text-red-300">500</h1>
      <p className="mt-2 text-gray-500">Something went wrong on our end</p>
      <a href="/" className="mt-6 text-sm font-medium text-blue-600 hover:underline">
        Back to Home
      </a>
    </div>
  );
}
